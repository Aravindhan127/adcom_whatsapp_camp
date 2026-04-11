from fastapi import APIRouter, Header, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.whatsapp_conversation import WhatsAppConversation
from app.models.contact import Contact
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
                        
                        # 1. Start/Update conversation
                        conv_data = ensure_conversation(db, wa_id, "service", meta_message_id=meta_id)
                        conv = conv_data["conversation"]
                        
                        # 2. Check for opt-out (STOP/UNSUBSCRIBE)
                        if handle_opt_out(db, wa_id, text):
                            # Optional: Send a confirmation message "You have been unsubscribed."
                            meta_send_msg(to=wa_id, text="You have been unsubscribed from our updates. Type START to subscribe again.")
                            return {"status": "contact_blocked"}
                        
                        # 3. Check for opt-in (START) - optional but good practice
                        if text.upper().strip() == "START":
                            contact = db.query(Contact).filter(Contact.phone_number == wa_id).first()
                            if contact:
                                contact.status = "valid"
                                db.commit()
                                meta_send_msg(to=wa_id, text="Welcome back! You have been re-subscribed.")
                                return {"status": "contact_resubscribed"}

                        # Flag as needs agent
                        conv.needs_agent = True
                        conv.last_user_reply_at = datetime.now(timezone.utc)
                        conv.window_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
                        
                        # Save incoming message
                        new_msg = WhatsAppMessage(
                            wa_id=wa_id, direction="in", message=text,
                            meta_message_id=meta_id, conversation_id=conv.id
                        )
                        db.add(new_msg)
                        db.commit()
                        
                        from app.core.websocket_manager import manager
                        await manager.notify_new_message(wa_id, {
                            "id": str(new_msg.id),
                            "text": text,
                            "timestamp": new_msg.created_at.isoformat() if new_msg.created_at else datetime.now().isoformat(),
                            "sender": "user"
                        })
                
                # 2. Handle Status Updates
                if "statuses" in value:
                    for status in value["statuses"]:
                        meta_id = status["id"]
                        new_status = status["status"] # 'delivered', 'read', 'failed'
                        msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_id).first()
                        if msg:
                            logger.info(f"Webhook Status Update: {meta_id} -> {new_status}")
                            msg.delivery_status = new_status
                            db.commit()

                            from app.core.websocket_manager import manager
                            await manager.broadcast({
                                "type": "status_update",
                                "meta_id": meta_id,
                                "status": new_status,
                                "wa_id": msg.wa_id
                            })
    
    return {"status": "success"}
