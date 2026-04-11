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
        # Find campaigns that are scheduled and the time has passed
        scheduled_campaigns = db.query(Campaign).filter(
            Campaign.status == "scheduled",
            Campaign.scheduled_at <= now
        ).all()

        for campaign in scheduled_campaigns:
            logger.info(f"Triggering scheduled campaign: {campaign.name} ({campaign.id})")
            if not is_within_limits(db):
                logger.warning(f"Meta limits reached, skipping scheduled campaign {campaign.id}")
                continue

            # Update status to running and start the run via service
            from app.services.campaign_service import start_campaign_run
            result = start_campaign_run(db, str(campaign.id))

            if "error" in result:
                logger.error(f"Failed to start scheduled campaign {campaign.id}: {result['error']}")
                # Revert status on failure so it can be retried
                campaign.status = "scheduled"
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

@celery_app.task(name="send_campaign_batch", bind=True, max_retries=3, default_retry_delay=60)
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
            
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == campaign.template_name).first()
        template_language = template.language if template else "en"

        # SAFETY CHECK: Ensure template exists and has components
        if template and template.components is None:
            template.components = []

        # 1. Template Status Syncing (Rule 11) - Check if template is still approved
        logger.info(f"Worker: Checking meta status for {campaign.template_name}...")
        meta_status = get_meta_templates_status()
        
        # Hardened Guard: Ensure meta_status is a dictionary before access
        if not isinstance(meta_status, dict):
            logger.error(f"Worker: Unexpected Meta response type: {type(meta_status)}. Raw: {meta_status}")
            meta_status = {"error": "Invalid API Response Type"}

        if isinstance(meta_status.get("data"), list):
            current_meta_tpl = next((t for t in meta_status["data"] if isinstance(t, dict) and t.get("name") == campaign.template_name), None)
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
            logger.warning(f"Worker: Could not get Meta template status: {meta_status.get('error', 'Unknown Error')}")

        # 2. Fetch contacts for this batch
        contacts = db.query(Contact).filter(Contact.list_id == campaign.contact_list_id).offset(offset).limit(limit).all()
        if not contacts:
            logger.info(f"Worker: No more contacts for campaign {campaign_id} at offset {offset}")
            return "No contacts in this batch"

        logger.info(f"Worker: Starting batch for run {run_id} ({len(contacts)} contacts)")
        success_batch, failed_batch, skipped_batch = 0, 0, 0
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

                # 1. Idempotency Protection (Rule: Never dual-send)
                if is_message_already_sent(db, campaign_id, phone):
                    logger.info(f"Worker: Skipping contact {phone}. Message already exists in DB for this campaign.")
                    skipped_batch += 1
                    continue

                # 2. Check for Opt-Out (STOP keyword)
                if is_contact_blocked(db, phone):
                    logger.info(f"Worker: Skipping blocked contact {phone}")
                    skipped_batch += 1
                    continue
                
                # Determine Message Category
                cat = template.category.lower() if template else "marketing"
                
                # Billing & Conversation Tracking
                billing_res = ensure_conversation(db, contact.phone_number, cat)
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
                            # Robust Media Detection (Rule: Differentiate Link vs Meta Handle)
                            media_payload = {}
                            # Handles usually start with 'h/' or are numeric IDs
                            is_handle = campaign.media_url.startswith("h/") or campaign.media_url.isdigit()
                            
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
                if campaign.template_params:
                    # Sequentiality Check: Meta requires variables in order {{1}}, {{2}}, ...
                    # We sort keys numerically: "1", "2", "3"
                    param_keys = sorted(campaign.template_params.keys(), key=lambda x: int(x) if x.isdigit() else 999)
                    body_parameters = []
                    
                    for pk in param_keys:
                        mapping = campaign.template_params[pk]
                        val = ""
                        
                        if isinstance(mapping, str) and mapping.startswith("contact."):
                            # Resolve from contact model
                            field_name = mapping.split(".")[1]
                            # Handle common aliases (e.g. name, company_name)
                            val = getattr(contact, field_name, "")
                        else:
                            # Static text for all contacts in this campaign
                            val = mapping
                            
                        body_parameters.append({"type": "text", "text": str(val) if val is not None else ""})
                    
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
                
                if "error" in response:
                    logger.error(f"Worker: Send FAILED for {contact.phone_number}: {response.get('error')}")
                    code = response.get("code")
                    
                    # Handle Rate & Account Limits
                    if code in [429, 131045, 131048]:
                        jitter = random.uniform(10, 60)
                        wait_time = (120 * (2 ** self.request.retries)) + jitter
                        raise self.retry(exc=Exception(f"Meta Capacity Limit {code}"), countdown=wait_time)

                    # Save failed log
                    msg = WhatsAppMessage(
                        wa_id=contact.phone_number, direction="out",
                        delivery_status="failed", campaign_id=campaign_id,
                        message_type="template", template_name=campaign.template_name,
                        meta_message_id=f"ERR_{code}_{contact.phone_number}",
                        status_error=str(response.get("error"))
                    )
                    db.add(msg)
                    failed_batch += 1
                else:
                    success_batch += 1
                    total_batch_cost_inr += msg_cost_inr
                    meta_id = response.get("messages", [{}])[0].get("id")
                    logger.debug(f"Worker: Message sent to {contact.phone_number} -> MetaID: {meta_id}")
                    
                    # Save outgoing log
                    msg = WhatsAppMessage(
                        wa_id=contact.phone_number, direction="out",
                        meta_message_id=meta_id, campaign_id=campaign_id,
                        message_type="template", template_name=campaign.template_name,
                        whatsapp_cost=msg_cost_inr,
                        delivery_status="sent"
                    )
                    db.add(msg)
            except Exception as item_err:
                logger.error(f"Worker: CRITICAL ERROR processing contact {contact.phone_number}: {str(item_err)}")
                failed_batch += 1
        
        # Update Run Stats
        run.processed_count += len(contacts)
        run.success_count += success_batch
        run.failed_count += failed_batch
        run.total_cost_inr += total_batch_cost_inr
        run.last_processed_offset = offset + len(contacts)
        
        # Update Campaign Stats
        campaign.total_cost_inr += total_batch_cost_inr
        db.commit()

        # Quality Risk check (Rule 10)
        risk_percentage = check_quality_risk(db)
        if risk_percentage > 20.0:
            run.status = "paused"
            run.failure_reason = f"High failure rate ({risk_percentage}%). Paused for safety."
            campaign.status = "paused"
            db.commit()
            return f"PAUSED: Quality Risk {risk_percentage}%"

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

        # Check if more contacts remain
        if run.processed_count < run.total_contacts:
            # Use last_processed_offset to ensure proper resume after failures
            next_offset = run.last_processed_offset
            logger.info(f"Worker: Batch done. Progress: {run.processed_count}/{run.total_contacts}. Queuing next batch at {next_offset}")
            send_campaign_batch.delay(run_id, campaign_id, next_offset, limit)
        else:
            logger.info(f"Worker: Campaign run {run_id} COMPLETED SUCCESSFULLLY.")
            run.status = "completed"
            campaign.status = "completed"
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
        # CRITICAL: Record the exact error in the DB so it is visible in the UI
        error_msg = f"Worker Exception: {str(exc)}"
        logger.error(error_msg)
        
        try:
            # Re-fetch records to avoid 'DetachedInstance' or 'stale' states after rollback
            run = db.query(CampaignRun).get(run_id)
            campaign = db.query(Campaign).get(campaign_id)
            if run:
                run.status = "failed"
                run.failure_reason = error_msg
            if campaign:
                campaign.status = "failed"
                campaign.failure_reason = error_msg
            db.commit()
            logger.info("Worker: Successfully recorded failure in database.")
        except Exception as db_err:
            logger.error(f"Worker: Failed to record failure in DB: {str(db_err)}")

        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
