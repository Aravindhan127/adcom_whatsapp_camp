import os
import json
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.whatsapp_conversation import WhatsAppConversation

from app.services.billing import ensure_conversation
from app.models.settings import SystemSettings

from app.services.meta_api import (
    send_whatsapp_message as meta_send_msg, 
    upload_media
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
    Update message status in the database based on Meta status webhooks.
    """
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_id).first()
    if msg:
        msg.delivery_status = status
        db.commit()
    return msg

def send_whatsapp_message(
    db: Session,
    to: str,
    text: Optional[str] = None,
    media_path: Optional[str] = None,
    media_type: str = "text"
):
    """
    Sends a live chat message (text or media) and tracks billing.
    """
    media_id = None
    if media_path and os.path.exists(media_path):
        upload_res = upload_media(media_path, media_type)
        if "id" in upload_res:
            media_id = upload_res["id"]
        else:
            return {"error": f"Media upload failed: {upload_res.get('error')}"}

    # Track Billing (Service Category for Live Chat replies)
    billing_res = ensure_conversation(db, to, "service")

    response_json = meta_send_msg(
        to=to,
        text=text,
        media_id=media_id,
        media_type=media_type
    )

    # Handle Meta API errors
    if "error" in response_json:
        error_msg = response_json.get("error", "Unknown error from Meta API")
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
