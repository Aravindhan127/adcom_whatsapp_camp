import os
import json
import uuid
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.whatsapp_conversation import WhatsAppConversation

from app.services.billing import ensure_conversation
from app.models.settings import SystemSettings
from app.models.organization import OrganizationConfig

from app.services.meta_api import (
    send_whatsapp_message as meta_send_msg, 
    upload_media,
    format_meta_error
)

from app.core.config import settings

def verify_whatsapp_token(hub_mode: str | None, hub_verify_token: str | None, hub_challenge: str | None):
    """
    Standard Meta Webhook verification.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.MY_VERIFY_TOKEN:
        return int(hub_challenge)
    return {"error": "Invalid verification token"}

def finalize_billing_on_delivery(db: Session, meta_id: str, status: str):
    """
    Update message status and finalize session window activation/billing based on status webhooks.
    """
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_id).first()
    if msg:
        msg.delivery_status = status
        db.commit()
        
        # 1. Open Session and Deduct Balance ONLY on successful delivery or read!
        if status in ["delivered", "read"]:
            conv = db.query(WhatsAppConversation).filter(WhatsAppConversation.id == msg.conversation_id).first()
            if not conv:
                import re
                wa_id_clean = re.sub(r"\D", "", msg.wa_id)
                conv = db.query(WhatsAppConversation).filter(
                    WhatsAppConversation.wa_id.ilike(f"%{wa_id_clean}%")
                ).order_by(WhatsAppConversation.started_at.desc()).first()
                
            if conv and conv.billing_status == "pending":
                if conv.cost_inr > 0:
                    settings_obj = SystemSettings.get_settings(db)
                    settings_obj.meta_balance_inr = round((settings_obj.meta_balance_inr or 0) - conv.cost_inr, 4)
                    settings_obj.meta_balance_usd = round((settings_obj.meta_balance_usd or 0) - conv.cost_usd, 4)
                
                now_utc = datetime.now(timezone.utc)
                conv.started_at = now_utc
                conv.window_expires_at = now_utc + timedelta(hours=24)
                conv.billing_status = "charged"
                conv.is_active = True
                db.commit()
                
                # Broadcast WebSocket update so UI updates the "ACTIVE" session time pill instantly!
                try:
                    from app.core.websocket_manager import manager
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(manager.broadcast({
                            "type": "status_update",
                            "meta_id": meta_id,
                            "status": status,
                            "wa_id": msg.wa_id,
                            "is_active": True
                        }))
                except Exception as ws_err:
                    pass
                
        # 2. Mark session failed/inactive if delivery failed
        elif status in ["failed", "cooldown"]:
            conv = db.query(WhatsAppConversation).filter(WhatsAppConversation.id == msg.conversation_id).first()
            if not conv:
                import re
                wa_id_clean = re.sub(r"\D", "", msg.wa_id)
                conv = db.query(WhatsAppConversation).filter(
                    WhatsAppConversation.wa_id.ilike(f"%{wa_id_clean}%")
                ).order_by(WhatsAppConversation.started_at.desc()).first()
                
            if conv:
                conv.billing_status = "failed"
                conv.is_active = False
                conv.window_expires_at = None
                db.commit()
                
                # Broadcast WebSocket update so UI updates session expired instantly!
                try:
                    from app.core.websocket_manager import manager
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(manager.broadcast({
                            "type": "status_update",
                            "meta_id": meta_id,
                            "status": status,
                            "wa_id": msg.wa_id,
                            "is_active": False
                        }))
                except Exception as ws_err:
                    pass
                
    return msg

def send_whatsapp_message(
    db: Session,
    to: str,
    organization_id: uuid.UUID,
    text: Optional[str] = None,
    media_path: Optional[str] = None,
    media_type: str = "text"
):
    """
    Sends a live chat message (text or media) and tracks billing.
    """
    # 1. Fetch Organization Credentials
    config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == organization_id).first()
    if not config or not config.access_token:
        # Fallback to system settings if allowed, or error out
        settings = SystemSettings.get_settings(db)
        if not settings.whatsapp_token:
             return {"error": "Organization has no Meta Access Token configured"}
        token = settings.whatsapp_token
        phone_id = settings.phone_number_id
    else:
        token = config.access_token
        phone_id = config.phone_number_id

    # 2. Upload Media if needed
    media_id = None
    if media_path and os.path.exists(media_path):
        upload_res = upload_media(file_path=media_path, media_type=media_type, token=token, phone_id=phone_id)
        if "id" in upload_res:
            media_id = upload_res["id"]
        else:
            return {"error": f"Media upload failed: {upload_res.get('error')}"}

    # 3. Track Billing (Service Category for Live Chat replies)
    billing_res = ensure_conversation(db, to, "service", organization_id=organization_id)

    # 4. Call Meta API with organization credentials
    response_json = meta_send_msg(
        token=token,
        phone_id=phone_id,
        to=to,
        text=text,
        media_id=media_id,
        media_type=media_type
    )

    # Handle Meta API errors
    if "error" in response_json:
        error_msg = format_meta_error(response_json)
        return {"error": error_msg}

    if "messages" in response_json:
        meta_id = response_json["messages"][0]["id"]
        # Save to DB
        msg = WhatsAppMessage(
            wa_id=to,
            direction="out",
            message=text,
            meta_message_id=meta_id,
            delivery_status="sent",
            message_type=media_type,
            media_id=media_id,
            whatsapp_cost=billing_res.get("cost_inr", 0.0)
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        # Broadcast for real-time (Rule: other agents see this)
        from app.core.websocket_manager import manager
        manager.publish_event("new_message", {
            "wa_id": to,
            "data": {
                "id": str(msg.id),
                "text": text if text else f"[Media: {media_type}]",
                "timestamp": datetime.now().isoformat(),
                "sender": "agent"
            }
        })

    return response_json
