from fastapi import APIRouter, Request, Depends, Query, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
import json
import os
import logging
from datetime import datetime, timezone
from app.core.database import get_db

logger = logging.getLogger("adcom-api")
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.whatsapp_conversation import WhatsAppConversation
from app.models.agent import Agent
from app.core.security import get_current_user, RoleChecker
from app.services.whatsapp_chat_service import finalize_billing_on_delivery, send_whatsapp_message, verify_whatsapp_token
from app.services.billing import ensure_conversation
from app.services.ai_brain import chat_with_knowledge
from app.services.brochure_service import handle_brochure_request
from app.core.websocket_manager import manager

# Access control workers
admin_only = RoleChecker(["admin"])
any_agent = get_current_user


router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

def normalize_wa_id(wa_id: str) -> str:
    """Normalize phone number to always start with + for consistency."""
    if wa_id and not wa_id.startswith('+'):
        return f'+{wa_id}'
    return wa_id

@router.get("/webhook")
async def whatsapp_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge")
):
    return verify_whatsapp_token(hub_mode, hub_verify_token, hub_challenge)


@router.post("/webhook")
async def receive_whatsapp(request: Request, db: Session = Depends(get_db)):
    # SECURITY: Validate content type and parse JSON safely
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        logger.warning(f"Webhook received invalid content-type: {content_type}")
        raise HTTPException(status_code=400, detail="Invalid content type")

    try:
        data = await request.json()
    except json.JSONDecodeError as e:
        logger.error(f"Webhook received invalid JSON: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    except Exception as e:
        logger.error(f"Webhook parsing error: {str(e)}")
        raise HTTPException(status_code=400, detail="Failed to parse request")
    
    if "entry" not in data or not data["entry"]:
        return {"status": "no entry"}
        
    entry = data["entry"][0]
    changes = entry.get("changes", [])[0]
    value = changes.get("value", {})

    # Handle Status Updates (Delivery Tracking - Rule 8)
    statuses = value.get("statuses")
    if statuses:
        for update in statuses:
            meta_id = update.get("id")
            new_status = update.get("status")
            msg = finalize_billing_on_delivery(db, meta_id, new_status)
            if msg:
                await manager.broadcast({
                    "type": "status_update",
                    "meta_id": meta_id,
                    "status": new_status,
                    "wa_id": msg.wa_id
                })
        return {"status": "delivery_updates_processed"}

    messages = value.get("messages")
    if not messages:
        return {"status": "no messages"}
        
    msg = messages[0]
    wa_id = normalize_wa_id(msg["from"])
    meta_message_id = msg.get("id")
    msg_type = msg.get("type", "text")
    
    user_text = ""
    if msg_type == "text":
        user_text = msg["text"]["body"].strip()
    elif msg_type == "button":
        user_text = msg["button"]["text"]
    elif msg_type == "interactive":
        interactive = msg.get("interactive", {})
        itype = interactive.get("type")
        if itype == "button_reply":
            user_text = interactive["button_reply"]["title"]
    
    # 1. Start/Resume Billing Window (Rule 1)
    billing = ensure_conversation(db, wa_id, "service", meta_message_id=meta_message_id)
    conversation_id = billing["conversation"].id if billing.get("conversation") else None
    
    # 2. Save incoming message (Rule 5)
    existing_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.meta_message_id == meta_message_id).first()
    if existing_msg:
        logger.info(f"Ignoring duplicate WhatsApp message: {meta_message_id}")
        return {"status": "already_processed", "meta_message_id": meta_message_id}

    incoming = WhatsAppMessage(
        wa_id=wa_id, direction="in", message=user_text,
        meta_message_id=meta_message_id, conversation_id=conversation_id, message_type=msg_type
    )
    db.add(incoming)
    db.commit()
    db.refresh(incoming)

    # 3. Notify real-time (Rule: Live Chat updates)
    await manager.notify_new_message(wa_id, {
        "id": str(incoming.id),
        "text": user_text,
        "timestamp": incoming.created_at.isoformat() if incoming.created_at else datetime.now().isoformat(),
        "sender": "user"
    })

    # 3. Handle Automated Brochure Request (Latest featuredev branch logic)
    if handle_brochure_request(db, wa_id, user_text):
        return {"status": "brochure_sent"}
    
    # 4. Automated Responses Disabled (Rule: User requested removal of LLM messages)
    # The AI Knowledge Assistant block has been removed.
    
    return {"status": "message_received", "conversation_id": conversation_id}
...
@router.get("/conversations", summary="List All Conversations")
def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    campaign_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    # Base subquery: Get the latest conversation ID for each NORMALIZED phone number
    # This ensures "one number, one time" even if stored with/without + prefix
    from sqlalchemy import case
    # Normalize wa_id in the subquery grouping
    normalized_wa_id = func.replace(WhatsAppConversation.wa_id, ' ', '')
    # We group by the normalized form to collapse +91xxx and 91xxx as same
    latest_conv_ids_subquery = db.query(func.max(WhatsAppConversation.id)).group_by(
        func.ltrim(WhatsAppConversation.wa_id, '+')
    )
    
    query = db.query(WhatsAppConversation).filter(WhatsAppConversation.id.in_(latest_conv_ids_subquery))
    
    if search:
        query = query.filter(WhatsAppConversation.wa_id.ilike(f"%{search}%"))
    
    if campaign_id:
        # Filter these latest conversations by whether they received a message from this campaign
        query = query.filter(
            WhatsAppConversation.wa_id.in_(
                db.query(WhatsAppMessage.wa_id).filter(WhatsAppMessage.campaign_id == campaign_id)
            )
        )
    
    total = query.count()
    items = query.order_by(WhatsAppConversation.started_at.desc()).offset(skip).limit(limit).all()
    
    enriched = []
    now = datetime.now(timezone.utc)
    for conv in items:
        last_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.conversation_id == conv.id).order_by(WhatsAppMessage.created_at.desc()).first()
        
        # Determine if the 24h window is still active
        is_active = False
        if conv.window_expires_at:
            is_active = conv.window_expires_at > now
            
        enriched.append({
            "sessionId": str(conv.id),
            "phoneNumber": normalize_wa_id(conv.wa_id),
            "lastMessage": last_msg.message if last_msg else "No messages",
            "timestamp": last_msg.created_at.isoformat() if last_msg else conv.started_at.isoformat(),
            "unreadCount": 0,
            "isActive": is_active,
            "windowExpiresAt": conv.window_expires_at.isoformat() if conv.window_expires_at else None
        })
    
    return {"total": total, "conversations": enriched}


@router.get("/conversation/{wa_id}", summary="Get Messages for Conversation")
def get_conversation_messages(
    wa_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    # Normalize wa_id and also search both +91xxx and 91xxx formats
    wa_id_normalized = normalize_wa_id(wa_id)
    wa_id_no_plus = wa_id_normalized.lstrip('+')
    messages = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.wa_id.in_([wa_id_normalized, wa_id_no_plus])
    ).order_by(WhatsAppMessage.created_at.desc()).offset(skip).limit(limit).all()
    
    formatted = [{
        "id": str(m.id),
        "text": m.message,
        "sender": "user" if m.direction == "in" else "agent",
        "timestamp": m.created_at.isoformat(),
        "type": m.message_type,
        "deliveryStatus": m.delivery_status,
        "mediaUrl": f"/whatsapp/media/{m.media_id}" if m.media_id else None
    } for m in reversed(messages)]
    
    return {"messages": formatted}

@router.post("/send-message")
async def send_message_route(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    data = await request.json()
    to = normalize_wa_id(data.get("to", ""))
    text = data.get("message")

    if not to or not text:
        raise HTTPException(status_code=400, detail="Missing 'to' or 'message'")

    res = send_whatsapp_message(db=db, to=to, text=text)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res.get("error", "Failed to send message"))
    return res

from fastapi import UploadFile, File, Form
import shutil
import uuid
from pathlib import Path

# Secure file upload configuration
ALLOWED_MEDIA_TYPES = {"image", "video", "audio", "document"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".mp3", ".pdf", ".doc", ".docx"}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB limit for WhatsApp

@router.post("/send-media")
async def send_media_route(
    to: str = Form(...),
    media_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    # 1. Validate media type
    if media_type.lower() not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid media_type. Allowed: {', '.join(ALLOWED_MEDIA_TYPES)}"
        )

    # 2. Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 3. Validate and check file size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB"
        )

    # 4. Create secure temporary directory
    temp_dir = Path("temp_media")
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 5. Use secure filename (UUID-based, no path traversal)
    secure_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = temp_dir / secure_filename

    try:
        # Write file content
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        # 6. Validate file is not empty and is a valid file
        if not file_path.exists() or file_path.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="Invalid or empty file")

        res = send_whatsapp_message(db=db, to=to, media_path=str(file_path), media_type=media_type)

        # Check for Meta API errors
        if "error" in res:
            raise HTTPException(status_code=400, detail=res.get("error", "Failed to send media message"))

        return res
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending media: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send media message")
    finally:
        # Cleanup: Always remove temp file
        if file_path.exists():
            file_path.unlink(missing_ok=True)

