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
from app.services.meta_api import send_template_message, get_meta_templates_status
from app.services.opt_out_service import is_contact_blocked
from app.services.restriction_service import is_within_limits, check_quality_risk
from app.services.billing import ensure_conversation
from celery.exceptions import MaxRetriesExceededError
from app.core.websocket_manager import manager

logger = logging.getLogger("adcom-api")

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

            # Update status to running and start the run via service
            # IMPORTANT: Pass scheduled_at=None so start_campaign_run_v2 is called immediately
            # Without this, the service would re-schedule instead of launching!
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
        # BE-FIX BE-16: Use template's actual language with 'en_US' fallback.
        # Previously used 'en' which is INVALID for Meta Messages API → caused error 132001.
        template_language = template.language if template else "en_US"
        if template_language == "en":  # Meta doesn't accept bare 'en', needs 'en_US'
            template_language = "en_US"
        logger.info(f"Worker: Template language resolved to '{template_language}' for '{campaign.template_name}'")

        # SAFETY CHECK: Ensure template exists and has components
        if template and template.components is None:
            template.components = []

        # 1. Template Status Syncing (Rule 11) - Check if template is still approved
        logger.info(f"Worker: Checking meta status for {campaign.template_name}...")
        meta_status = get_meta_templates_status()
        
        # Hardened Guard: Ensure meta_status is a dictionary before access
        if not isinstance(meta_status, dict):
            logger.error(f"Worker: Unexpected Meta response type: {type(meta_status)}. Raw: {meta_status}")
            meta_status = {"error": str(meta_status)} # BE-FIX: was missing str() or check

        meta_data = meta_status.get("data")
        if isinstance(meta_data, list):
            current_meta_tpl = next((t for t in meta_data if isinstance(t, dict) and t.get("name") == campaign.template_name), None)
            if current_meta_tpl and current_meta_tpl.get("status") not in ("APPROVED", "ACTIVE"):
                error_reason = f"Meta Template Status: {current_meta_tpl.get('status')}"
                logger.warning(f"Worker: Aborting. Template {campaign.template_name} not approved: {error_reason}")
                run.status = "paused"
                run.failure_reason = error_reason
                campaign.status = "paused"
                campaign.failure_reason = error_reason
                db.commit()
                return f"ABORTED: Template '{campaign.template_name}' is not APPROVED on Meta"
        else:
            error_info = meta_status.get("error", "Unknown Error")
            logger.warning(f"Worker: Could not get Meta template status: {error_info}")

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
                billing_res = ensure_conversation(db, contact.phone_number, cat, commit=False)
                msg_cost_inr = billing_res.get("cost_inr", 0.0)
                
                # Anti-Spam Human-like delay (Rule 7)
                time.sleep(random.uniform(0.1, 0.3))

                # 3. Build Template Components (Variables and Media)
                message_components = []
                
                # Handle Media Header if present
                if campaign.media_url and template and template.components:
                    header_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "HEADER"), None)
                    if header_comp:
                        media_format = header_comp.get("format", "").lower()
                        if media_format in ["image", "video", "document"]:
                            # Robust Media Detection (Rule: Differentiate Link vs Meta ID/Handle)
                            media_payload = {}
                            
                            # Meta handles can be numeric or alphanumeric (e.g., '1:abc...', '4:xyz...', or 'h/...')
                            # If it's NOT a URL, we treat it as an ID/Handle.
                            is_handle = not str(campaign.media_url).lstrip().lower().startswith(("http://", "https://"))
                            
                            if is_handle:
                                media_payload = {"id": campaign.media_url}
                            else:
                                media_payload = {"link": campaign.media_url}

                            message_components.append({
                                "type": "header",
                                "parameters": [
                                    {
                                        "type": media_format,
                                        media_format: media_payload
                                    }
                                ]
                            })
                            logger.info(f"Worker: Injected {media_format} header ({'ID' if is_handle else 'Link'}) for {contact.phone_number}. Payload: {json.dumps(media_payload)}")

                # Handle Body Parameters (Variables mapping)
                # BE-FIX: Detect actual variable count needed by template (Rule: Prevent #132000 mismatch)
                body_comp = next((c for c in (template.components or []) if c.get("type", "").upper() == "BODY"), None)
                required_var_count = 0
                if body_comp and "text" in body_comp:
                    required_var_count = len(re.findall(r"\{\{\d+\}\}", body_comp["text"]))

                body_parameters = []
                if campaign.template_params:
                    # Sequentiality Check: Meta requires variables in order {{1}}, {{2}}, ...
                    param_keys = sorted(campaign.template_params.keys(), key=lambda x: int(x) if x.isdigit() else 999)
                    
                    for pk in param_keys:
                        mapping = campaign.template_params[pk]
                        val = ""
                        
                        if isinstance(mapping, str) and mapping.startswith("contact."):
                            field_name = mapping.split(".")[1]
                            if field_name == "category" and not hasattr(contact, "category"):
                                field_name = "customer_category"
                            val = getattr(contact, field_name, "")
                        else:
                            val = mapping
                            
                        body_parameters.append({"type": "text", "text": str(val) if val is not None else ""})
                
                # BE-FIX: Filling gaps if campaign params < required template vars
                # This ensures we always send the correct NUMBER of params, even if mappings are missing.
                while len(body_parameters) < required_var_count:
                    missing_idx = len(body_parameters) + 1
                    logger.warning(f"Worker: Param mismatch for {phone}. Missing variable {{{{{missing_idx}}}}}. Injecting fallback.")
                    body_parameters.append({"type": "text", "text": " "}) 
                
                if body_parameters:
                    message_components.append({
                        "type": "body",
                        "parameters": body_parameters
                    })
                    logger.debug(f"Worker: Resolved {len(body_parameters)} body params for {contact.phone_number}")

                # Send Message
                response = send_template_message(
                    to=contact.phone_number,
                    template_name=campaign.template_name,
                    components=message_components,
                    language=template_language
                )
                
                # Defensive check: ensure response is a dict (not str) before calling .get()
                if not isinstance(response, dict):
                    logger.error(f"Worker: Unexpected response type {type(response)} for {phone}: {response}")
                    response = {"error": str(response), "code": None}

                if "error" in response:
                    error_msg = response.get("error")
                    code = response.get("code")
                    logger.error(f"Worker: Send FAILED for {phone}: {error_msg} (Code: {code})")
                    
                    # Store a human-readable but detailed error reason
                    status_error = f"({code}) {error_msg}" if code else error_msg
                    
                    # Handle Rate & Account Limits
                    if code in [429, 131045, 131048]:
                        # Rate limit exponential backoff: 2, 4, 8 mins
                        wait_time = (120 * (2 ** self.request.retries)) + random.uniform(5, 15)
                        raise self.retry(exc=Exception(f"Meta Rate Limit {code}"), countdown=wait_time)

                    # Save failed log
                    # Format: ERR_<CODE>_<PHONE>_<CAMPAIGN_SHORT>_<TS>
                    unique_err_id = f"ERR_{code}_{phone}_{campaign_id[:5]}_{int(time.time())}"
                    
                    # If send failed, ROLLBACK the pending billing conversation to avoid leakage
                    db.rollback() 
                    
                    # Re-add the failure log in a clean state
                    # Capture the detailed Meta error if available
                    meta_id = unique_err_id
                    
                    # Extract error details from the response (which is in 'res_data' or 'response')
                    res_data = response if isinstance(response, dict) else {}
                    raw_err = res_data.get("error", "Unknown Meta Error")
                    
                    # Store with code in parens for frontend mapping
                    status_error = f"({code}) {raw_err}"

                    msg = WhatsAppMessage(
                        wa_id=phone, direction="out",
                        delivery_status="failed", campaign_id=campaign_id,
                        message_type="template", template_name=campaign.template_name,
                        meta_message_id=meta_id,
                        status_error=status_error
                    )
                    db.add(msg)
                    db.commit() # Save the failure record immediately
                    
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
            except Exception as item_err:
                error_str = str(item_err)
                logger.error(f"Worker: ERROR processing contact {contact.phone_number}: {error_str}")
                
                # Check for 'Connection aborted' (10053) specifically
                if "Connection aborted" in error_str or "10053" in error_str:
                    logger.warning("Worker: Network connection was aborted by host. Retrying batch...")
                    # Immediate retry with small jitter to re-establish connection
                    raise self.retry(exc=item_err, countdown=random.uniform(1, 3))

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
            if risk_percentage > 20.0:
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
