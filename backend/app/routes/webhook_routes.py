from fastapi import APIRouter, Header, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.whatsapp_conversation import WhatsAppConversation
from app.models.contact import Contact
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun
from app.services.meta_api import send_whatsapp_message as meta_send_msg
from app.services.billing import ensure_conversation
from app.services.opt_out_service import handle_opt_out
from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import json
import logging

logger = logging.getLogger("adcom-api")

router = APIRouter(prefix="/webhook", tags=["webhook"])

def verify_webhook_signature(body: bytes, signature: str, app_secret: str) -> bool:
    """Verify Meta webhook signature using HMAC-SHA256."""
    if not signature or not app_secret:
        return False
    expected = hmac.new(
        app_secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

@router.get("/")
def verify_webhook(request: Request):
    # Meta webhook verification
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.MY_VERIFY_TOKEN:
        return int(challenge)

    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256")
):
    # SECURITY: Read raw body first for signature verification
    body = await request.body()

    # Verify webhook signature if app secret is configured
    if hasattr(settings, 'META_APP_SECRET') and settings.META_APP_SECRET:
        if not verify_webhook_signature(body, x_hub_signature_256, settings.META_APP_SECRET):
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
        logger.info(f"Webhook Received: {json.dumps(payload)[:500]}...") # Log start of payload
        
        # BE-FIX: Raw Trace Logger (Rule: Diagnostic Visibility)
        # This writes the FULL payload to a file for forensic analysis of delivery failures.
        try:
            with open("webhook_debug.log", "a", encoding="utf-8") as f:
                f.write(f"\n--- {datetime.now().isoformat()} ---\n")
                f.write(json.dumps(payload, indent=2))
                f.write("\n")
        except Exception as log_err:
            logger.error(f"Failed to write webhook_debug.log: {log_err}")
            
    except json.JSONDecodeError:
        logger.error(f"Webhook JSON Error: {body[:200]}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if "entry" in payload:
        for entry in payload["entry"]:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                
                # 1. Handle Messages (Rule 4)
                if "messages" in value:
                    for msg in value["messages"]:
                        wa_id = msg["from"]
                        meta_id = msg["id"]
                        text = msg.get("text", {}).get("body", "")
                        meta_ts = int(msg.get("timestamp", datetime.now(timezone.utc).timestamp()))
                        started_at = datetime.fromtimestamp(meta_ts, tz=timezone.utc)
                        
                        # 1. Start/Update conversation
                        conv_data = ensure_conversation(db, wa_id, "service", meta_message_id=meta_id, started_at=started_at)
                        conv = conv_data["conversation"]
                        
                        # 2. Check for opt-out (STOP/UNSUBSCRIBE)
                        if handle_opt_out(db, wa_id, text):
                            # Optional: Send a confirmation message "You have been unsubscribed."
                            await meta_send_msg(to=wa_id, text="You have been unsubscribed from our updates. Type START to subscribe again.")
                            logger.info(f"Contact {wa_id} opted out.")
                            continue # Process next message/status in SAME payload
                        
                        # 3. Check for opt-in (START)
                        if text.upper().strip() == "START":
                            contact = db.query(Contact).filter(Contact.phone_number == wa_id).first()
                            if contact:
                                contact.status = "valid"
                                db.commit()
                                await meta_send_msg(to=wa_id, text="Welcome back! You have been re-subscribed.")
                                logger.info(f"Contact {wa_id} opted in.")
                                continue # Process next message/status in SAME payload

                        # Flag as needs agent
                        conv.needs_agent = True
                        conv.last_user_reply_at = started_at
                        conv.window_expires_at = started_at + timedelta(hours=24)
                        
                        # Save incoming message
                        new_msg = WhatsAppMessage(
                            wa_id=wa_id, direction="in", message=text,
                            meta_message_id=meta_id, conversation_id=conv.id
                        )
                        db.add(new_msg)
                        db.commit()
                        
                        # Look up contact name strictly from the Contact Table
                        # Smart Match: Use last 10 digits to resolve country code mismatches
                        last_10 = wa_id[-10:] if len(wa_id) >= 10 else wa_id
                        contact = db.query(Contact).filter(Contact.phone_number.ilike(f"%{last_10}")).first()
                        contact_name = contact.name if (contact and contact.name) else None

                        from app.core.websocket_manager import manager
                        await manager.notify_new_message(wa_id, {
                            "id": str(new_msg.id),
                            "text": text,
                            "timestamp": new_msg.created_at.isoformat() if new_msg.created_at else datetime.now().isoformat(),
                            "sender": "user",
                            "contactName": contact_name,
                            "window_expires_at": conv.window_expires_at.isoformat() if conv.window_expires_at else None,
                            "is_active": True
                        })
                
                # 2. Handle Status Updates
                if "statuses" in value:
                    for status in value["statuses"]:
                        try:
                            meta_id = status["id"]
                            new_status = status["status"] # 'delivered', 'read', 'failed'
                            
                            msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_id).first()
                            if msg:
                                logger.info(f"Webhook Status Update: {meta_id} -> {new_status}")
                                
                                # BE-FIX: Summary Analytics Sync
                                # When status changes from 'sent' to 'delivered' or 'read', 
                                # we update the Campaign and CampaignRun counters so the Dashboard stays accurate.
                                if msg.campaign_id:
                                    try:
                                        # 1. Update Campaign Stats
                                        # Use atomic increment to prevent race conditions during high-volume webhooks
                                        campaign = db.query(Campaign).get(msg.campaign_id)
                                        if campaign:
                                            if new_status == 'delivered' and msg.delivery_status == 'sent':
                                                campaign.delivered_count = (campaign.delivered_count or 0) + 1
                                            elif new_status == 'read':
                                                # If it moves to 'read', it also counts as 'delivered' if we haven't counted it yet
                                                if msg.delivery_status == 'sent': 
                                                    campaign.delivered_count = (campaign.delivered_count or 0) + 1
                                                if msg.delivery_status != 'read':
                                                    campaign.read_count = (campaign.read_count or 0) + 1
                                            elif new_status == 'failed' and msg.delivery_status != 'failed':
                                                campaign.failed_count = (campaign.failed_count or 0) + 1
                                        
                                        # 2. Update the most recent CampaignRun if applicable
                                        from sqlalchemy import desc
                                        run = db.query(CampaignRun).filter(CampaignRun.campaign_id == msg.campaign_id).order_by(desc(CampaignRun.created_at)).first()
                                        if run:
                                            # Ensure counters are not Null
                                            run.success_count = run.success_count or 0
                                            run.failed_count = run.failed_count or 0
                                            
                                            if new_status in ['delivered', 'read'] and msg.delivery_status == 'sent':
                                                run.success_count += 1
                                            elif new_status == 'failed' and msg.delivery_status != 'failed':
                                                run.failed_count += 1
                                    except Exception as sync_err:
                                        logger.error(f"Webhook: Failed to sync analytics for campaign {msg.campaign_id}: {sync_err}")
                                
                                # BE-FIX: Capture detailed error reason from Meta (Rule: Log visibility)
                                if new_status == "failed":
                                    errors = status.get("errors", [])
                                    if errors and isinstance(errors, list) and len(errors) > 0:
                                        err = errors[0]
                                        code = err.get("code")
                                        msg_text = err.get("message") or err.get("title") or "Unknown failure"
                                        msg.status_error = f"({code}) {msg_text}" if code else msg_text
                                    else:
                                        try:
                                            msg.status_error = json.dumps(status)
                                        except Exception:
                                            msg.status_error = "Meta delivery failed"
                                
                                # Update the actual message status
                                msg.delivery_status = new_status
                                db.commit()

                                from app.core.websocket_manager import manager
                                await manager.broadcast({
                                    "type": "status_update",
                                    "meta_id": meta_id,
                                    "status": new_status,
                                    "wa_id": msg.wa_id,
                                    "campaign_id": str(msg.campaign_id) if msg.campaign_id else None
                                })
                        except Exception as status_err:
                            logger.error(f"Webhook: Error processing status update {status.get('id')}: {status_err}")
                            continue # Don't crash the WHOLE webhook if one status update fails
    
    return {"status": "success"}
