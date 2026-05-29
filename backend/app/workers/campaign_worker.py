import time
import json
import random
import logging
import re
from datetime import datetime, timezone, timedelta
import requests
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import SessionLocal
from app.core.celery_app import celery_app
import app.models
from app.models.contact import Contact
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.template import WhatsAppTemplate
from app.models.organization import OrganizationConfig
from app.services.meta_api import send_template_message, get_meta_templates_status, format_meta_error
from app.services.opt_out_service import is_contact_blocked
from app.services.restriction_service import is_within_limits, check_quality_risk
from app.services.billing import ensure_conversation
from celery.exceptions import MaxRetriesExceededError
from app.core.websocket_manager import manager

logger = logging.getLogger("adcom-api")

# ──────────────────────────────────────────────────────────────
# Meta API Error Code Registry
# Source: https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
# ──────────────────────────────────────────────────────────────
META_ERROR_CODES = {
    # Auth errors — campaign must abort
    0:      ("FATAL",   "Authentication failed. The access token is invalid or expired. Update it in Infrastructure settings."),
    3:      ("FATAL",   "API permission denied. Verify your app has the required WhatsApp permissions."),
    10:     ("FATAL",   "Permission denied. The access token is missing required permissions."),
    190:    ("FATAL",   "Access token has expired. Generate a new permanent token and update Infrastructure settings."),
    368:    ("FATAL",   "WhatsApp Business Account temporarily blocked for policy violations. Check Meta Business Manager."),
    131031: ("FATAL",   "Account has been locked for policy violations. Contact Meta Support."),
    131042: ("FATAL",   "Billing/payment issue with your WhatsApp Business Account. Check your payment method in Meta."),
    131005: ("FATAL",   "Access denied. Check that the access token has all required permissions."),
    # Template errors — campaign must abort
    132000: ("FATAL",   "Template variable count mismatch. The number of parameters sent doesn't match the template."),
    132001: ("FATAL",   "Template not found or not approved on Meta. Run 'Sync Meta' and verify the template status."),
    132015: ("FATAL",   "Template is paused by Meta due to low quality. Edit and re-submit the template."),
    132016: ("FATAL",   "Template is permanently disabled by Meta due to repeated low quality. Create a new template."),
    132007: ("FATAL",   "Template content violates a WhatsApp policy."),
    132012: ("FATAL",   "Template parameter format mismatch. Check variable types in the template."),
    132005: ("FATAL",   "Template translated text is too long."),
    # Rate limit errors — retry with backoff
    4:      ("RATE",    "App API rate limit reached. Slowing down and retrying."),
    80007:  ("RATE",    "WhatsApp Business Account rate limit reached. Retrying after cooldown."),
    130429: ("RATE",    "Cloud API message throughput limit reached. Retrying after cooldown."),
    131048: ("RATE",    "Spam rate limit hit. Too many messages were blocked/flagged as spam. Retrying."),
    131056: ("RATE",    "Too many messages sent to the same recipient in a short period. Retrying."),
    133016: ("RATE",    "Account register/deregister rate limit exceeded. Retrying."),
    # Contact/recipient errors — skip contact, do NOT abort campaign
    131026: ("SKIP",    "Recipient not on WhatsApp or has not accepted Meta's Terms of Service."),
    131047: ("SKIP",    "Re-engagement required: more than 24 hours since the recipient last replied. Cannot send template."),
    131049: ("SKIP",    "Meta chose not to deliver this message to protect ecosystem engagement."),
    131050: ("SKIP",    "Recipient has opted out of marketing messages from this business."),
    131021: ("SKIP",    "Sender and recipient phone number are the same."),
    131037: ("SKIP",    "Business phone number display name not yet approved."),
    130472: ("SKIP",    "User's number is part of a Meta experiment. Message not sent."),
    # Temporary/service errors — retry
    1:      ("RETRY",   "Unknown API error. Possibly a temporary Meta server issue."),
    2:      ("RETRY",   "Meta API service temporarily unavailable. Retrying."),
    131000: ("RETRY",   "Unknown Meta error. Retrying."),
    131016: ("RETRY",   "Meta service temporarily unavailable. Retrying."),
    131057: ("RETRY",   "WhatsApp Business Account is in maintenance mode. Retrying."),
    133004: ("RETRY",   "Meta server temporarily unavailable. Retrying."),
    # Media errors — campaign must abort
    131052: ("FATAL",   "Media file too big. Max file size supported is 100MB. Please use a smaller file."),
    131053: ("FATAL",   "Media MIME type mismatch or upload error. Check that your file extension matches its content and the file is not corrupted."),
}

def classify_meta_error(code):
    """
    Returns (severity, human_reason) for a given Meta error code.
    Severity: FATAL (abort campaign) | RATE (retry with backoff) | SKIP (skip contact) | RETRY (generic retry)
    """
    if code is None:
        return ("RETRY", "Unknown error (no code returned by Meta).")
    entry = META_ERROR_CODES.get(int(code) if str(code).isdigit() else code)
    if entry:
        return entry
    # Default for unknown codes
    return ("RETRY", f"Meta error code {code}. The message could not be delivered.")

def is_phone_valid(phone: str) -> bool:
    """Validate E.164 phone format."""
    if not phone: return False
    # E.164: + followed by 1 to 15 digits.
    # Our DB usually stores without + but we handle both.
    pattern = r"^\+?[1-9]\d{1,14}$"
    return bool(re.match(pattern, phone))

def is_message_already_sent(db: Session, campaign_id: str, phone_number: str) -> bool:
    """Check if a message was already sent to this contact for this campaign."""
    return db.query(WhatsAppMessage).filter(
        WhatsAppMessage.campaign_id == campaign_id,
        WhatsAppMessage.wa_id == phone_number,
        WhatsAppMessage.delivery_status != "failed"
    ).first() is not None

@celery_app.task(name="check_scheduled_campaigns")
def check_scheduled_campaigns():
    """
    Periodic task to check for scheduled campaigns and start them if the time has come.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        logger.info(f"Worker: Checking for scheduled campaigns... (now={now})")
        # Find campaigns that are scheduled and the time has passed
        scheduled_campaigns = db.query(Campaign).filter(
            Campaign.status == "scheduled",
            Campaign.scheduled_at <= now,
            Campaign.is_deleted == False
        ).all()

        for campaign in scheduled_campaigns:
            logger.info(f"Triggering scheduled campaign: {campaign.name} ({campaign.id})")
            if not is_within_limits(db):
                logger.warning(f"Meta limits reached, skipping scheduled campaign {campaign.id}")
                continue

            # ANTI-DUPLICATE GUARD: Mark campaign as 'running' BEFORE launching.
            # Without this, if the Beat fires again (or two workers run simultaneously)
            # before start_campaign_run_v2 commits, the campaign is still 'scheduled'
            # and gets launched TWICE → duplicate messages.
            campaign.status = "running"
            try:
                db.commit()
            except Exception as lock_err:
                db.rollback()
                logger.warning(f"Could not lock campaign {campaign.id} for launch (likely a race): {lock_err}")
                continue  # Skip — another worker already picked it up

            from app.services.campaign_service import start_campaign_run_v2
            result = start_campaign_run_v2(db, str(campaign.id))

            if "error" in result:
                error_msg = result['error']
                logger.error(f"Failed to start scheduled campaign {campaign.id}: {error_msg}")
                # BE-FIX: Mark as failed if it can't be started (e.g. no contacts, invalid template)
                # This prevents endless retry loops every minute.
                campaign.status = "failed"
                campaign.failure_reason = error_msg
                db.commit()


    except Exception as e:
        logger.error(f"Error in check_scheduled_campaigns: {str(e)}")
        db.rollback()
    finally:
        db.close()

@celery_app.task(name="check_on_hold_campaigns")
def check_on_hold_campaigns():
    """
    Cron task to resume campaigns that were put 'on_hold' due to rate limits.
    """
    db = SessionLocal()
    try:
        on_hold_since_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        on_hold_runs = db.query(CampaignRun).filter(
            CampaignRun.status == "on_hold",
            CampaignRun.on_hold_since <= on_hold_since_threshold
        ).all()

        for run in on_hold_runs:
            campaign = db.query(Campaign).get(run.campaign_id)
            if not campaign: continue
            
            logger.info(f"Resuming 'on_hold' campaign: {campaign.name}")
            run.status = "running"
            campaign.status = "running"
            run.on_hold_since = None  # Clear the on_hold timestamp
            db.commit()

            # Trigger the next batch from last_processed_offset to avoid duplicates
            next_offset = run.last_processed_offset or run.processed_count
            send_campaign_batch.delay(str(run.id), str(campaign.id), next_offset, 100)
            
    except Exception as e:
        logger.error(f"Error in check_on_hold_campaigns: {str(e)}")
        db.rollback()
    finally:
        db.close()

@celery_app.task(name="send_campaign_batch", bind=True, max_retries=3)
def send_campaign_batch(self, run_id: str, campaign_id: str, offset: int, limit: int):
    """
    Processes a batch of contacts for a campaign run.
    """
    db = SessionLocal()
    try:
        run = db.query(CampaignRun).get(run_id)
        if not run or run.status == "paused":
            return "Run paused or not found"

        campaign = db.query(Campaign).get(campaign_id)
        if not campaign:
            return "Campaign not found"
            
        # BE-FIX: Abort if campaign was deleted while task was in queue
        if campaign.is_deleted:
            logger.warning(f"Worker: Aborting run {run_id}. Campaign {campaign_id} has been soft-deleted.")
            run.status = "paused" # Effectively stops further batches
            db.commit()
            return "ABORTED: Campaign was deleted"
            
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == campaign.template_name).first()
        
        # Dynamically register template tracked links in Redis before starting the batch
        if template and template.variable_mappings and "tracked_links" in template.variable_mappings:
            try:
                import json
                redis_client = celery_app.backend.client
                for sc, dest in template.variable_mappings["tracked_links"].items():
                    redis_key = f"shortcode:{sc}"
                    redis_client.set(
                        redis_key,
                        json.dumps({
                            "destination_url": dest,
                            "campaign_id": str(campaign_id)
                        })
                    )
                    logger.info(f"Worker: Dynamically registered shortcode mapping '{redis_key}' -> '{dest}' in Redis")
            except Exception as redis_err:
                logger.error(f"Worker: Failed to dynamically register shortcodes in Redis: {redis_err}")
                
        # Use template's actual language with 'en_US' fallback.
        # Note: We now respect 'en' if the template was approved as 'en'.
        template_language = template.language if (template and template.language) else "en_US"
        logger.info(f"Worker: Template language resolved to '{template_language}' for '{campaign.template_name}'")

        # SAFETY CHECK: Ensure template exists and has components
        if template and template.components is None:
            template.components = []

        # 0. Fetch Organization Credentials
        config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == campaign.organization_id).first()
        if not config or not config.access_token:
            # Fallback to system settings OR error
            from app.models.settings import SystemSettings
            sys_settings = SystemSettings.get_settings(db)
            if not sys_settings.whatsapp_token:
                logger.error(f"Worker: Aborting. No Meta credentials for Org {campaign.organization_id}")
                run.status = "paused"
                run.failure_reason = "No Meta Access Token configured"
                campaign.status = "paused"
                db.commit()
                return "ABORTED: No Meta Access Token"
            token = sys_settings.whatsapp_token
            waba = sys_settings.whatsapp_business_id
            phone_id = sys_settings.phone_number_id
        else:
            token = config.access_token
            waba = config.whatsapp_business_id
            phone_id = config.phone_number_id

        # 1. Template Status Syncing (Rule 11) - Check if template is still approved
        logger.info(f"Worker: Checking meta status for {campaign.template_name}...")
        meta_status = get_meta_templates_status(token=token, waba_id=waba)
        
        # Hardened Guard: Ensure meta_status is a dictionary before access
        if not isinstance(meta_status, dict):
            logger.error(f"Worker: Unexpected Meta response type: {type(meta_status)}. Raw: {meta_status}")
            meta_status = {"error": str(meta_status)} # BE-FIX: was missing str() or check

        # Smart Approved Language Matcher
        meta_data = meta_status.get("data")
        approved_languages = []
        if isinstance(meta_data, list):
            for t in meta_data:
                if isinstance(t, dict) and t.get("name") == campaign.template_name and t.get("status") in ("APPROVED", "ACTIVE"):
                    approved_languages.append(t.get("language"))
        
        if approved_languages:
            logger.info(f"Worker: Approved languages for template '{campaign.template_name}' on Meta: {approved_languages}")
            # If target language is in approved languages, keep it.
            if template_language in approved_languages:
                logger.info(f"Worker: Target language '{template_language}' is approved on Meta.")
            else:
                # Try soft mapping, e.g. en_US -> en, or en -> en_US
                matched_lang = None
                for lang in approved_languages:
                    if lang.split('_')[0] == template_language.split('_')[0]:
                        matched_lang = lang
                        break
                
                if matched_lang:
                    logger.info(f"Worker: Soft-matched target '{template_language}' to approved '{matched_lang}'")
                    template_language = matched_lang
                else:
                    # Fallback to the first approved language
                    logger.warning(f"Worker: Target language '{template_language}' not approved on Meta. Falling back to first approved language: '{approved_languages[0]}'")
                    template_language = approved_languages[0]
        else:
            # Fallback checks if we couldn't list or match any approved language
            if isinstance(meta_data, list):
                unapproved_tpl = next((t for t in meta_data if isinstance(t, dict) and t.get("name") == campaign.template_name), None)
                if unapproved_tpl:
                    error_reason = f"Meta Template Status: {unapproved_tpl.get('status')}"
                    logger.warning(f"Worker: Aborting. Template {campaign.template_name} is not APPROVED/ACTIVE on Meta. (Status: {unapproved_tpl.get('status')})")
                    run.status = "paused"
                    run.failure_reason = error_reason
                    campaign.status = "paused"
                    campaign.failure_reason = error_reason
                    db.commit()
                    return f"ABORTED: Template '{campaign.template_name}' is not APPROVED on Meta"
            else:
                error_info = meta_status.get("error", "Unknown Error")
                logger.warning(f"Worker: Could not get Meta template status: {error_info}")

        # Initialize media URL to ID cache and dynamic upload helper
        media_url_to_id_cache = {}
        
        def resolve_media_to_id(media_input: str, m_format: str) -> tuple[str, bool]:
            """
            Resolves a media input (which could be a URL or a handle/ID) to a valid Meta Media ID.
            Returns (media_id, is_handle).
            """
            if not media_input or str(media_input).lower() == "none":
                return media_input, False
                
            is_url = str(media_input).lstrip().lower().startswith(("http://", "https://", "/"))
            if not is_url:
                return media_input, True
                
            download_url = media_input
            if download_url.startswith("/"):
                download_url = f"http://localhost:8000{download_url}"
                
            if download_url in media_url_to_id_cache:
                return media_url_to_id_cache[download_url], True
                
            logger.info(f"Worker: Dynamic resolve/upload for '{download_url}' (format: {m_format})...")
            try:
                import tempfile
                import os
                from app.services.meta_api import upload_media
                
                resp = requests.get(download_url, timeout=30)
                if resp.status_code == 200:
                    url_path = download_url.split('?')[0]
                    suffix = os.path.splitext(url_path)[1] or ".jpg"
                    
                    content_type = resp.headers.get("Content-Type", "").lower()
                    m_type = m_format.lower()
                    if not m_type or m_type not in ["image", "video", "audio", "document"]:
                        if "video" in content_type:
                            m_type = "video"
                        elif "audio" in content_type:
                            m_type = "audio"
                        elif "pdf" in content_type or "document" in content_type:
                            m_type = "document"
                        else:
                            m_type = "image"
                    
                    file_bytes = resp.content
                    if m_type == "image":
                        try:
                            from PIL import Image
                            from io import BytesIO
                            
                            img = Image.open(BytesIO(resp.content))
                            if img.format not in ["JPEG", "PNG"]:
                                logger.info(f"Worker: Normalizing image format '{img.format}' to JPEG...")
                                if img.mode in ("RGBA", "LA", "P"):
                                    img = img.convert("RGB")
                                jpeg_io = BytesIO()
                                img.save(jpeg_io, format="JPEG", quality=90)
                                file_bytes = jpeg_io.getvalue()
                                suffix = ".jpg"
                        except Exception as pil_err:
                            logger.warning(f"Worker: PIL check failed: {pil_err}. Using raw bytes.")
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_f:
                        temp_f.write(file_bytes)
                        temp_path = temp_f.name
                        
                    upload_res = upload_media(temp_path, m_type, token=token, phone_id=phone_id)
                    os.remove(temp_path)
                    
                    if "error" in upload_res:
                        raise ValueError(f"Meta upload error: {upload_res['error']}")
                        
                    media_id = upload_res.get("id")
                    if media_id:
                        logger.info(f"Worker: Auto-upload successful. Got Media ID: {media_id}")
                        media_url_to_id_cache[download_url] = media_id
                        return media_id, True
                    else:
                        raise ValueError("Meta did not return a Media ID in upload response.")
                else:
                    raise ValueError(f"HTTP error {resp.status_code} downloading media.")
            except Exception as upload_err:
                logger.exception(f"Worker: Dynamic upload failed for '{download_url}'.")
                raise upload_err

        # 2. Fetch contacts for this batch
        contacts = db.query(Contact).filter(Contact.list_id == campaign.contact_list_id).offset(offset).limit(limit).all()
        if not contacts:
            logger.info(f"Worker: No more contacts for campaign {campaign_id} at offset {offset}")
            return "No contacts in this batch"

        logger.info(f"Worker: Starting batch for run {run_id} ({len(contacts)} contacts) at offset {offset}")
        success_batch, failed_batch, skipped_batch = 0, 0, 0
        actually_processed = 0  # BE-FIX BE-7: Count only sent+failed (not skipped)
        total_batch_cost_inr = 0.0
        
        for i, contact in enumerate(contacts):
            phone = contact.phone_number
            try:
                # 0. Phone Validation (Rule: Pre-validate to save Meta credits)
                if not is_phone_valid(phone):
                    logger.warning(f"Worker: Skipping invalid phone format '{phone}' for contact {contact.id}")
                    # Log as local failure
                    msg = WhatsAppMessage(
                        wa_id=phone, direction="out",
                        delivery_status="failed", campaign_id=campaign_id,
                        message_type="template", template_name=campaign.template_name,
                        meta_message_id=f"LOCAL_INVALID_{phone}",
                        status_error="Invalid phone format"
                    )
                    db.add(msg)
                    failed_batch += 1
                    continue

                # BE-FIX BE-10: Mid-batch pause check (every 50 contacts to balance responsiveness vs overhead)
                if i > 0 and i % 50 == 0:
                    db.refresh(run)
                    if run.status == "paused":
                        logger.info(f"Worker: Mid-batch pause detected at contact #{i} of batch. Stopping early.")
                        break

                # 1. Idempotency Protection (Rule: Never dual-send)
                if is_message_already_sent(db, campaign_id, phone):
                    logger.info(f"Worker: Skipping {phone} — already sent for this campaign.")
                    skipped_batch += 1
                    continue  # BE-FIX BE-7: skipped = NOT counted in processed

                # 2. Check for Opt-Out (STOP keyword)
                if is_contact_blocked(db, phone):
                    logger.info(f"Worker: Skipping blocked contact {phone}")
                    skipped_batch += 1
                    continue  # BE-FIX BE-7: skipped = NOT counted in processed
                
                # Determine Message Category
                cat = template.category.lower() if template else "marketing"
                
                # Billing Tracking (Deferred commit - Rule: Only charge if send succeeds)
                billing_res = ensure_conversation(db, contact.phone_number, cat, organization_id=campaign.organization_id, commit=False)
                msg_cost_inr = billing_res.get("cost_inr", 0.0)
                
                # Anti-Spam Human-like delay (Rule 7)
                time.sleep(random.uniform(0.1, 0.3))

                # 3. Build Template Components (Variables and Media)
                message_components = []
                
                # A. Handle Main Header (Standard)
                header_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "HEADER"), None)
                if header_comp:
                    media_format = header_comp.get("format", "").lower()
                    if media_format in ["image", "video", "document"]:
                        use_media = campaign.media_url or header_comp.get("example", {}).get("header_handle", [None])[0]
                        if use_media:
                            try:
                                resolved_media, is_handle = resolve_media_to_id(use_media, media_format)
                                media_payload = {"id": resolved_media}
                            except Exception:
                                # Fallback to standard URL link parameter if upload fails for standard templates
                                is_handle = not str(use_media).lstrip().lower().startswith(("http://", "https://"))
                                media_payload = {"id": use_media} if is_handle else {"link": use_media}
                            
                            message_components.append({
                                "type": "header",
                                "parameters": [{"type": media_format, media_format: media_payload}]
                            })

                # B. Handle Main Body (Standard)
                body_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "BODY"), None)
                if body_comp:
                    text = body_comp.get("text", "")
                    required_var_count = len(re.findall(r"\{\{\d+\}\}", text))
                    body_parameters = []
                    
                    if required_var_count > 0:
                        if campaign.template_params:
                            # Only keep keys that are digits (variables) and ignore metadata like "tracked_links"
                            param_keys = sorted(
                                [k for k in campaign.template_params.keys() if k.isdigit()],
                                key=lambda x: int(x)
                            )
                            for pk in param_keys:
                                mapping = campaign.template_params[pk]
                                val = ""
                                if isinstance(mapping, str) and mapping.startswith("contact."):
                                    field_name = mapping.split(".")[1]
                                    val = getattr(contact, field_name, "")
                                else:
                                    val = mapping
                                body_parameters.append({"type": "text", "text": str(val) if val is not None else ""})
                        
                        while len(body_parameters) < required_var_count:
                            body_parameters.append({"type": "text", "text": " "}) 
                    
                    # Always append body if it exists, even with empty parameters (required for some templates)
                    message_components.append({
                        "type": "body",
                        "parameters": body_parameters[:required_var_count]
                    })

                # C. Handle Buttons (Dynamic URL Tracking & Quick Reply Payloads)
                buttons_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "BUTTONS"), None)
                if buttons_comp:
                    for btn_idx, btn in enumerate(buttons_comp.get("buttons", [])):
                        if btn.get("type", "").upper() == "URL" and "{{" in btn.get("url", ""):
                            # Dynamic URL button requires parameters!
                            # We automatically inject the recipient's phone number as the text parameter for {{1}}
                            message_components.append({
                                "type": "button",
                                "sub_type": "url",
                                "index": btn_idx,
                                "parameters": [{"type": "text", "text": str(phone)}]
                            })
                            logger.info(f"Worker: Injected phone '{phone}' as parameter for dynamic URL button index {btn_idx}")
                        elif btn.get("type", "").upper() == "QUICK_REPLY" and btn.get("id"):
                            message_components.append({
                                "type": "button",
                                "sub_type": "quick_reply",
                                "index": btn_idx,
                                "parameters": [{"type": "payload", "payload": btn.get("id")}]
                            })

                # D. Handle Carousel Component
                carousel_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "CAROUSEL"), None)
                if carousel_comp:
                    carousel_cards = []
                    for idx, card in enumerate(carousel_comp.get("cards", [])):
                        card_components = []
                        for ccomp in card.get("components", []):
                            cc_type = ccomp.get("type", "").upper()
                            if cc_type == "HEADER":
                                media_format = ccomp.get("format", "").lower()
                                if media_format in ["image", "video"]:
                                    # Priority: 1. Card example, 2. Campaign global media (only for 1st card)
                                    use_media = ccomp.get("example", {}).get("header_handle", [None])[0]
                                    if idx == 0 and campaign.media_url:
                                        use_media = campaign.media_url
                                    
                                    if use_media and str(use_media).lower() != "none":
                                        resolved_media, is_handle = resolve_media_to_id(use_media, media_format)
                                        media_payload = {"id": resolved_media}
                                        card_components.append({
                                            "type": "header",
                                            "parameters": [{"type": media_format, media_format: media_payload}]
                                        })
                            elif cc_type == "BODY":
                                text = ccomp.get("text", "")
                                vars_in_text = re.findall(r"\{\{\d+\}\}", text)
                                if vars_in_text:
                                    card_body_params = []
                                    for v in vars_in_text:
                                        card_body_params.append({"type": "text", "text": contact.name or "Customer"})
                                    card_components.append({
                                        "type": "body",
                                        "parameters": card_body_params
                                    })
                            elif cc_type == "BUTTONS":
                                # Carousel cards often have 1 or 2 buttons. 
                                # We must include them in the message payload to ensure they appear.
                                # Each button in a carousel card is indexed.
                                for b_idx, btn in enumerate(ccomp.get("buttons", [])):
                                    btn_params = []
                                    if btn.get("type", "").upper() == "QUICK_REPLY" and btn.get("id"):
                                        btn_params = [{"type": "payload", "payload": btn.get("id")}]
                                    card_components.append({
                                        "type": "button",
                                        "sub_type": "url" if btn.get("type", "").upper() == "URL" else "quick_reply",
                                        "index": b_idx,
                                        "parameters": btn_params
                                    })
                        
                        if card_components:
                            carousel_cards.append({
                                "card_index": idx,
                                "components": card_components
                            })
                    
                    if carousel_cards:
                        message_components.append({
                            "type": "carousel",
                            "cards": carousel_cards
                        })

                # Send Message
                response = send_template_message(
                    to=contact.phone_number,
                    template_name=campaign.template_name,
                    components=message_components,
                    language=template_language,
                    token=token,
                    phone_id=phone_id
                )
                
                # Defensive check: ensure response is a dict (not str) before calling .get()
                if not isinstance(response, dict):
                    logger.error(f"Worker: Unexpected response type {type(response)} for {phone}: {response}")
                    response = {"error": str(response), "code": None}

                code = response.get("code")
                if "error" in response:
                    error_msg = response.get("error")
                    logger.error(f"Worker: Send FAILED for {phone}: {error_msg} (Code: {code})")
                    
                    # Store a human-readable but detailed error reason
                    status_error = format_meta_error(response)
                    
                    # Handle Rate, Account Limits, and Temporary Network Errors
                    if code in [429, 131045, 131048, 1, 2, 131000, 131016, 131057, 133004]:
                        # Exponential backoff: 2, 4, 8 mins
                        wait_time = (120 * (2 ** self.request.retries)) + random.uniform(5, 15)
                        logger.warning(f"Worker: Transient error {code}. Retrying in {wait_time}s... (Attempt {self.request.retries + 1}/3)")
                        raise self.retry(exc=Exception(f"Transient Meta Error {code}"), countdown=wait_time)

                    # Check if it is a Cooldown error (Code 131049)
                    is_cooldown = (code == 131049 or "131049" in str(error_msg))
                    
                    delivery_status = "cooldown" if is_cooldown else "failed"
                    if is_cooldown:
                        status_error = "(131049) Quality Blocked. Cooldown active (Retry recommended after 24 hours)."
                        meta_id = f"COOLDOWN_{phone}_{campaign_id[:5]}_{int(time.time())}"
                    else:
                        meta_id = f"ERR_{code}_{phone}_{campaign_id[:5]}_{int(time.time())}"

                    msg = WhatsAppMessage(
                        wa_id=phone, direction="out",
                        delivery_status=delivery_status, campaign_id=campaign_id,
                        message_type="template", template_name=campaign.template_name,
                        meta_message_id=meta_id,
                        status_error=status_error
                    )
                    db.add(msg)
                    db.commit() # Save the failure/cooldown record immediately
                    
                    if is_cooldown:
                        skipped_batch += 1
                    else:
                        failed_batch += 1
                    
                    actually_processed += 1
                else:
                    success_batch += 1
                    actually_processed += 1  # BE-FIX BE-7
                    total_batch_cost_inr += msg_cost_inr
                    
                    # Safe retrieval of messages list and meta ID
                    msgs = response.get("messages", [])
                    meta_id = msgs[0].get("id") if (isinstance(msgs, list) and len(msgs) > 0 and isinstance(msgs[0], dict)) else f"SUCCESS_{phone}"
                    
                    logger.debug(f"Worker: Message sent to {phone} -> MetaID: {meta_id}")
                    
                    # Save outgoing log
                    msg = WhatsAppMessage(
                        wa_id=phone, direction="out",
                        meta_message_id=meta_id, campaign_id=campaign_id,
                        message_type="template", template_name=campaign.template_name,
                        whatsapp_cost=msg_cost_inr,
                        delivery_status="sent"
                    )
                    db.add(msg)
                    db.commit() # BE-FIX: Commit immediately to allow webhook status sync
            except Exception as item_err:
                error_str = str(item_err)
                logger.error(f"Worker: ERROR processing contact {contact.phone_number}: {error_str}")
                
                # Check for 'Connection aborted' (10053) specifically
                if "Connection aborted" in error_str or "10053" in error_str:
                    logger.warning("Worker: Network connection was aborted by host. Retrying batch...")
                    # Immediate retry with small jitter to re-establish connection
                    raise self.retry(exc=item_err, countdown=random.uniform(1, 3))

                # BE-FIX: Save the local error message to DB so it shows in dashboard
                meta_id = f"LOCAL_ERR_{phone}_{int(time.time())}"
                msg = WhatsAppMessage(
                    wa_id=phone, direction="out",
                    delivery_status="failed", campaign_id=campaign_id,
                    message_type="template", template_name=campaign.template_name,
                    meta_message_id=meta_id,
                    status_error=error_str
                )
                db.add(msg)
                db.commit()

                failed_batch += 1
                actually_processed += 1  # BE-FIX BE-7: count failed as processed (not skipped)
        
        # BE-FIX BE-7: Update Run Stats — only count actually_processed (sent+failed), NOT skipped
        run.processed_count += actually_processed
        run.success_count += success_batch
        run.failed_count += failed_batch
        run.total_cost_inr += total_batch_cost_inr
        run.last_processed_offset = offset + len(contacts)  # Offset always advances by full batch length
        logger.info(f"Worker: Batch stats — sent={success_batch}, failed={failed_batch}, skipped={skipped_batch}, processed={actually_processed}")
        
        # Update Campaign Stats
        campaign.total_cost_inr += total_batch_cost_inr
        db.commit()

        # 4. Notify UI of progress via Redis Pub/Sub
        manager.publish_event("campaign_progress", {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "processed": run.processed_count,
            "total": run.total_contacts,
            "success": run.success_count,
            "failed": run.failed_count,
            "status": run.status
        })

        # Check if more contacts remain (compare offset-based, not processed_count-based)
        if run.last_processed_offset < run.total_contacts:
            # BE-FIX: Quality Risk check (Rule 10)
            # ONLY pause if we actually have more messages left to send.
            # If the campaign is done, marking it as paused is redundant and logically wrong.
            risk_percentage = check_quality_risk(db)
            if risk_percentage > 99.0:
                run.status = "paused"
                run.failure_reason = f"High failure rate ({risk_percentage}%). Paused for safety."
                campaign.status = "paused"
                db.commit()
                
                # Notify UI of the pause
                manager.publish_event("campaign_progress", {
                    "campaign_id": campaign_id,
                    "run_id": run_id,
                    "processed": run.processed_count,
                    "total": run.total_contacts,
                    "success": run.success_count,
                    "failed": run.failed_count,
                    "status": "paused"
                })
                return f"PAUSED: Quality Risk {risk_percentage}%"

            next_offset = run.last_processed_offset
            logger.info(f"Worker: Queuing next batch at offset {next_offset} (total={run.total_contacts})")
            send_campaign_batch.delay(run_id, campaign_id, next_offset, limit)
        else:
            logger.info(f"Worker: Campaign run {run_id} COMPLETED SUCCESSFULLY.")
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)    # BE-FIX BE-12: was never set
            campaign.status = "completed"
            campaign.completed_at = datetime.now(timezone.utc)  # BE-FIX BE-12: was never set
            db.commit()
            
            # Final Completion notification
            manager.publish_event("campaign_progress", {
                "campaign_id": campaign_id,
                "run_id": run_id,
                "processed": run.processed_count,
                "total": run.total_contacts,
                "success": run.success_count,
                "failed": run.failed_count,
                "status": "completed"
            })

        return f"Batch {offset} done: {success_batch} ok, {failed_batch} err"
    
    except MaxRetriesExceededError:
        # Move to ON HOLD for 24h
        run = db.query(CampaignRun).get(run_id)
        campaign = db.query(Campaign).get(campaign_id)
        run.status = "on_hold"
        run.on_hold_since = datetime.now(timezone.utc)
        run.failure_reason = "Meta Rate Limit Exceeded (Retries used up)"
        campaign.status = "on_hold"
        db.commit()
        return "Max retries exceeded. Campaign Put ON HOLD."
    except Exception as exc:
        db.rollback()
        # Calculate next retry delay: 4, 8, 16 minutes
        retry_intervals = [240, 480, 960]
        curr_retry = self.request.retries
        wait_time = retry_intervals[curr_retry] if curr_retry < len(retry_intervals) else 960
        
        error_msg = f"Worker Retry #{curr_retry + 1} in {wait_time//60}m: {str(exc)}"
        logger.warning(error_msg)
        
        # Maintain 'running' status while retrying to avoid user confusion
        # We only set to 'failed' in the MaxRetriesExceededError block below.
        
        raise self.retry(exc=exc, countdown=wait_time)
    finally:
        db.close()

@celery_app.task(name="retry_campaign_cooldown")
def retry_campaign_cooldown(campaign_id: str):
    """
    Background task to retry all messages in 'cooldown' status for a specific campaign.
    Validates WABA status and quality rating via Meta API before sending.
    """
    db = SessionLocal()
    try:
        from app.models.campaign import Campaign
        from app.models.campaign_run import CampaignRun
        from app.models.whatsapp_chat_model import WhatsAppMessage
        from app.models.contact import Contact
        from app.models.template import WhatsAppTemplate
        from app.models.organization import OrganizationConfig
        from app.services.meta_api import send_template_message, check_phone_number_health
        from app.services.billing import ensure_conversation
        
        campaign = db.query(Campaign).get(campaign_id)
        if not campaign:
            logger.error(f"Cooldown Retry: Campaign {campaign_id} not found.")
            return "Campaign not found"
            
        # Re-fetch credentials
        config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == campaign.organization_id).first()
        if not config or not config.access_token:
            from app.models.settings import SystemSettings
            sys_settings = SystemSettings.get_settings(db)
            token = sys_settings.whatsapp_token
            phone_id = sys_settings.phone_number_id
        else:
            token = config.access_token
            phone_id = config.phone_number_id
            
        # 1. Query Meta API to check if the phone number has recovered from restriction/low quality
        logger.info(f"Cooldown Retry: Checking health status for Phone ID: {phone_id}...")
        health = check_phone_number_health(token, phone_id)
        
        # Determine if we should allow sending based on Meta status check
        is_healthy = True
        status_reason = ""
        
        if "error" in health:
            logger.warning(f"Cooldown Retry: Could not check WABA health: {health['error']}. Falling back to time-based safety.")
            status_reason = f"Health check skipped: {health['error']}"
        else:
            status = health.get("status")
            quality = health.get("quality_rating")
            logger.info(f"Cooldown Retry: Phone status is '{status}', Quality rating is '{quality}'")
            
            # WABA phone statuses: CONNECTED, FLAGGED, RESTRICTED, UNVERIFIED etc.
            if status == "RESTRICTED" or quality == "RED":
                is_healthy = False
                status_reason = f"Meta Account restricted (Status: {status}, Quality: {quality})"
                
        # Get all cooldown messages for this campaign
        cooldown_msgs = db.query(WhatsAppMessage).filter(
            WhatsAppMessage.campaign_id == campaign_id,
            WhatsAppMessage.delivery_status == "cooldown"
        ).all()
        
        if not cooldown_msgs:
            logger.info(f"Cooldown Retry: No cooldown messages found for campaign {campaign_id}.")
            return "No messages to retry"
            
        if not is_healthy:
            logger.warning(f"Cooldown Retry: Aborting retry run. Reason: {status_reason}")
            # Update all cooldown messages to state this checked error
            for msg in cooldown_msgs:
                msg.status_error = f"Meta Cooldown active: {status_reason}. Will retry again."
            db.commit()
            return f"Aborted: {status_reason}"
            
        # Resolved Template
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == campaign.template_name).first()
        template_language = template.language if (template and template.language) else "en_US"
        
        logger.info(f"Cooldown Retry: Resending {len(cooldown_msgs)} cooldown messages for campaign {campaign_id}...")
        success_count = 0
        failed_count = 0
        
        for msg in cooldown_msgs:
            try:
                # Find the associated contact
                contact = db.query(Contact).filter(Contact.phone_number == msg.wa_id, Contact.list_id == campaign.contact_list_id).first()
                if not contact:
                    # Fallback lookup
                    contact = db.query(Contact).filter(Contact.phone_number == msg.wa_id).first()
                    
                if not contact:
                    msg.delivery_status = "failed"
                    msg.status_error = "Contact not found for retry"
                    failed_count += 1
                    continue
                    
                # Reconstruct components
                message_components = []
                
                # A. Handle Header
                header_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "HEADER"), None)
                if header_comp:
                    media_format = header_comp.get("format", "").lower()
                    if media_format in ["image", "video", "document"]:
                        use_media = campaign.media_url or header_comp.get("example", {}).get("header_handle", [None])[0]
                        if use_media:
                            is_url = str(use_media).lstrip().lower().startswith(("http://", "https://", "/"))
                            if is_url:
                                from app.services.meta_api import upload_media
                                download_url = use_media
                                if download_url.startswith("/"):
                                    download_url = f"http://localhost:8000{download_url}"
                                    
                                import tempfile
                                import os
                                resp = requests.get(download_url, timeout=30)
                                if resp.status_code == 200:
                                    url_path = download_url.split('?')[0]
                                    suffix = os.path.splitext(url_path)[1] or ".jpg"
                                    file_bytes = resp.content
                                    # Normalize Image via Pillow
                                    if media_format == "image":
                                        try:
                                            from PIL import Image
                                            from io import BytesIO
                                            img = Image.open(BytesIO(resp.content))
                                            if img.format not in ["JPEG", "PNG"]:
                                                if img.mode in ("RGBA", "LA", "P"):
                                                    img = img.convert("RGB")
                                                jpeg_io = BytesIO()
                                                img.save(jpeg_io, format="JPEG", quality=90)
                                                file_bytes = jpeg_io.getvalue()
                                                suffix = ".jpg"
                                        except Exception:
                                            pass
                                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_f:
                                        temp_f.write(file_bytes)
                                        temp_path = temp_f.name
                                    upload_res = upload_media(temp_path, media_format, token=token, phone_id=phone_id)
                                    os.remove(temp_path)
                                    media_id = upload_res.get("id")
                                    media_payload = {"id": media_id} if media_id else {"link": use_media}
                                else:
                                    media_payload = {"link": use_media}
                            else:
                                media_payload = {"id": use_media}
                                
                            message_components.append({
                                "type": "header",
                                "parameters": [{"type": media_format, media_format: media_payload}]
                            })

                # B. Handle Body
                body_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "BODY"), None)
                if body_comp:
                    text = body_comp.get("text", "")
                    required_var_count = len(re.findall(r"\{\{\d+\}\}", text))
                    body_parameters = []
                    if required_var_count > 0:
                        if campaign.template_params:
                            # Only keep keys that are digits (variables) and ignore metadata like "tracked_links"
                            param_keys = sorted(
                                [k for k in campaign.template_params.keys() if k.isdigit()],
                                key=lambda x: int(x)
                            )
                            for pk in param_keys:
                                mapping = campaign.template_params[pk]
                                val = ""
                                if isinstance(mapping, str) and mapping.startswith("contact."):
                                    field_name = mapping.split(".")[1]
                                    val = getattr(contact, field_name, "")
                                else:
                                    val = mapping
                                body_parameters.append({"type": "text", "text": str(val) if val is not None else ""})
                        
                        while len(body_parameters) < required_var_count:
                            body_parameters.append({"type": "text", "text": contact.name or "Customer"})
                            
                        message_components.append({
                            "type": "body",
                            "parameters": body_parameters[:required_var_count]
                        })

                # C. Handle Buttons (Retry Loop)
                buttons_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "BUTTONS"), None)
                if buttons_comp:
                    for btn_idx, btn in enumerate(buttons_comp.get("buttons", [])):
                        if btn.get("type", "").upper() == "URL" and "{{" in btn.get("url", ""):
                            message_components.append({
                                "type": "button",
                                "sub_type": "url",
                                "index": btn_idx,
                                "parameters": [{"type": "text", "text": str(contact.phone_number)}]
                            })
                        elif btn.get("type", "").upper() == "QUICK_REPLY" and btn.get("id"):
                            message_components.append({
                                "type": "button",
                                "sub_type": "quick_reply",
                                "index": btn_idx,
                                "parameters": [{"type": "payload", "payload": btn.get("id")}]
                            })

                # Send
                response = send_template_message(
                    to=contact.phone_number,
                    template_name=campaign.template_name,
                    components=message_components,
                    language=template_language,
                    token=token,
                    phone_id=phone_id
                )
                
                if not isinstance(response, dict):
                    response = {"error": str(response)}
                    
                if "error" in response:
                    err_msg = response.get("error", "Retry failed")
                    code = response.get("code")
                    logger.error(f"Cooldown Retry: Resend failed for {msg.wa_id}: {err_msg}")
                    if code == 131049 or "131049" in str(err_msg):
                        msg.status_error = f"(131049) Cooldown still active. Will auto-retry again later."
                    else:
                        msg.delivery_status = "failed"
                        msg.status_error = format_meta_error(response)
                        failed_count += 1
                else:
                    msgs = response.get("messages", [])
                    meta_id = msgs[0].get("id") if (msgs and len(msgs) > 0) else f"SUCCESS_RETRY_{msg.wa_id}"
                    logger.info(f"Cooldown Retry: Resend successful for {msg.wa_id} -> MetaID: {meta_id}")
                    
                    msg.delivery_status = "sent"
                    msg.meta_message_id = meta_id
                    msg.status_error = None
                    success_count += 1
                    
            except Exception as item_err:
                logger.error(f"Cooldown Retry: Error processing contact {msg.wa_id}: {str(item_err)}")
                msg.delivery_status = "failed"
                msg.status_error = f"Retry exception: {str(item_err)}"
                failed_count += 1
                
        # Commit all changes to DB
        db.commit()
        logger.info(f"Cooldown Retry Completed: Campaign {campaign_id} -> {success_count} succeeded, {failed_count} failed")
        
        # Notify progress changes to UI
        manager.publish_event("campaign_progress", {
            "campaign_id": campaign_id,
            "status": campaign.status,
            "cooldown_retry_completed": True,
            "success_added": success_count,
            "failed_added": failed_count
        })
        return f"Completed retry: {success_count} success, {failed_count} failed"
        
    except Exception as e:
        logger.exception(f"Cooldown Retry: Exception in main retry runner for campaign {campaign_id}")
        db.rollback()
        return f"Error: {str(e)}"
    finally:
        db.close()

@celery_app.task(name="auto_process_all_cooldowns")
def auto_process_all_cooldowns():
    """
    Periodic task to find all active campaigns with 'cooldown' messages
    and trigger the retry task for them automatically.
    """
    db = SessionLocal()
    try:
        from app.models.whatsapp_chat_model import WhatsAppMessage
        from sqlalchemy import distinct
        
        # Find all distinct campaigns that currently have 'cooldown' messages
        active_cooldown_campaign_ids = db.query(distinct(WhatsAppMessage.campaign_id)).filter(
            WhatsAppMessage.delivery_status == "cooldown"
        ).all()
        
        if not active_cooldown_campaign_ids:
            logger.info("Cooldown Scheduler: No campaigns with active cooldown messages.")
            return "No campaigns to process"
            
        logger.info(f"Cooldown Scheduler: Found {len(active_cooldown_campaign_ids)} campaigns with cooldown messages. Triggering retries...")
        for row in active_cooldown_campaign_ids:
            camp_id = str(row[0])
            if camp_id and camp_id != "None":
                logger.info(f"Cooldown Scheduler: Auto-queueing retry for campaign {camp_id}")
                retry_campaign_cooldown.delay(camp_id)
                
        return f"Queued retries for {len(active_cooldown_campaign_ids)} campaigns"
    except Exception as e:
        logger.error(f"Cooldown Scheduler: Exception in periodic checker: {str(e)}")
        return f"Error: {str(e)}"
    finally:
        db.close()


@celery_app.task(name="app.workers.campaign_worker.send_link_click_acknowledgment")
def send_link_click_acknowledgment(wa_id: str, destination_url: str, campaign_id: str):
    """Sends an AI generated acknowledgment to a user when they click a tracked link."""
    db = SessionLocal()
    try:
        from app.models.campaign import Campaign
        from app.models.organization import OrganizationConfig
        from app.services.meta_api import send_whatsapp_message as meta_send_msg
        from app.services.ai_brain import chat_with_knowledge
        from app.models.whatsapp_chat_model import WhatsAppMessage
        from app.services.billing import ensure_conversation
        
        campaign = db.query(Campaign).get(campaign_id)
        if not campaign:
            return "Campaign not found"
            
        config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == campaign.organization_id).first()
        if not config or not config.access_token:
            from app.models.settings import SystemSettings
            sys_settings = SystemSettings.get_settings(db)
            token = sys_settings.whatsapp_token
            phone_id = sys_settings.phone_number_id
        else:
            token = config.access_token
            phone_id = config.phone_number_id
            
        # Use AI Brain to generate a context aware thank you acknowledgment
        logger.info(f"Link click AI acknowledgment: Generating response for {wa_id}...")
        prompt = f"The user just clicked our tracked URL link: '{destination_url}' in their chat. Please write a very short, polite, and helpful thank you/acknowledgment message (1-2 sentences maximum) to send to them."
        ai_res = chat_with_knowledge(
            query=prompt,
            context="You are a professional assistant. When a user clicks our website link, thank them politely."
        )
        ack_text = ai_res.get("response", "Thank you for visiting our link! Let us know if you need any assistance.")
        
        # Send message
        meta_send_msg(to=wa_id, text=ack_text, token=token, phone_id=phone_id)
        
        # Save in DB message log
        conv_data = ensure_conversation(db, wa_id, "service", organization_id=campaign.organization_id)
        conv = conv_data["conversation"]
        
        ai_msg = WhatsAppMessage(
            wa_id=wa_id, direction="out", message=ack_text,
            conversation_id=conv.id, campaign_id=campaign.id
        )
        db.add(ai_msg)
        db.commit()
        
        # Notify WebSocket UI
        from app.core.websocket_manager import manager
        import asyncio
        
        # Broadcast real-time websocket message to update chat screen instantly
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast({
                "type": "new_message",
                "wa_id": wa_id,
                "message": {
                    "id": str(ai_msg.id),
                    "text": ack_text,
                    "sender": "agent",
                    "timestamp": ai_msg.created_at.isoformat() if ai_msg.created_at else datetime.now().isoformat()
                }
            }), loop)
        else:
            loop.run_until_complete(manager.broadcast({
                "type": "new_message",
                "wa_id": wa_id,
                "message": {
                    "id": str(ai_msg.id),
                    "text": ack_text,
                    "sender": "agent",
                    "timestamp": ai_msg.created_at.isoformat() if ai_msg.created_at else datetime.now().isoformat()
                }
            }))
        
        return "Success"
    except Exception as e:
        logger.error(f"Failed to send link click acknowledgment: {str(e)}")
        return str(e)
    finally:
        db.close()
