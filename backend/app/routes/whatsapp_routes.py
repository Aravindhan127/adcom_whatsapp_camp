from fastapi import APIRouter, Request, Depends, Query, HTTPException, status, Response
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
from app.core.security import get_current_user, get_current_user_flexible, RoleChecker, user_has_bypass
from app.services.whatsapp_chat_service import finalize_billing_on_delivery, send_whatsapp_message, verify_whatsapp_token
from app.services.billing import ensure_conversation
from app.services.ai_brain import chat_with_knowledge
from app.services.brochure_service import handle_brochure_request
from app.core.websocket_manager import manager
from app.services.meta_api import get_meta_media_url, get_meta_media_content

# Access control workers
admin_only = RoleChecker(["admin"])
any_agent = get_current_user


router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

def normalize_wa_id(wa_id: str) -> str:
    """Normalize phone number to digits only for consistency."""
    if not wa_id:
        return ""
    # Remove any non-digit characters (like +, spaces, dashes)
    import re
    return re.sub(r"\D", "", wa_id)

@router.get("/webhook")
async def whatsapp_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge")
):
    return verify_whatsapp_token(hub_mode, hub_verify_token, hub_challenge)


@router.post("/webhook", include_in_schema=False)
async def receive_whatsapp_deprecated(request: Request, db: Session = Depends(get_db)):
    """
    DEPRECATED: Use /api/webhook/ instead for better analytics and AI support.
    """
    logger.warning("Redundant Webhook Hit: /api/whatsapp/webhook is deprecated. Switch to /api/webhook/")
    return {"status": "deprecated", "message": "Please use /api/webhook/"}
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
    # Base subquery: Get the latest conversation ID for each UNIQUE phone number (last 10 digits)
    # This is the most robust way to collapse +91, 91, and other variants.
    latest_conv_ids_subquery = db.query(func.max(WhatsAppConversation.id)).group_by(
        func.right(WhatsAppConversation.wa_id, 10)
    )
    
    query = db.query(WhatsAppConversation).filter(WhatsAppConversation.id.in_(latest_conv_ids_subquery))
    
    # Isolation: Filter by organization unless superadmin
    if not user_has_bypass(current_user):
        query = query.filter(WhatsAppConversation.organization_id == current_user.organization_id)
    
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
    
    from app.models.contact import Contact

    enriched = []
    now = datetime.now(timezone.utc)
    for conv in items:
        last_msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.conversation_id == conv.id).order_by(WhatsAppMessage.created_at.desc()).first()
        
        # Look up contact name (scoped to org)
        last_10 = conv.wa_id[-10:] if len(conv.wa_id) >= 10 else conv.wa_id
        contact_query = db.query(Contact).filter(Contact.phone_number.ilike(f"%{last_10}"))
        if not user_has_bypass(current_user):
            contact_query = contact_query.filter(Contact.organization_id == current_user.organization_id)
        contact = contact_query.first()
        contact_name = contact.name if contact else None

        # Determine if the 24h window is still active
        is_active = False
        if conv.window_expires_at:
            is_active = conv.window_expires_at > now
            
        enriched.append({
            "sessionId": str(conv.id),
            "phoneNumber": normalize_wa_id(conv.wa_id),
            "contactName": contact_name,
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
    # Use last 10 digits suffix matching for history to be extra robust
    last_10 = wa_id.replace('+', '').replace(' ', '')[-10:] if len(wa_id) >= 10 else wa_id
    messages = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.wa_id.ilike(f"%{last_10}")
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

    res = send_whatsapp_message(db=db, to=to, organization_id=current_user.organization_id, text=text)
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
    # 0. Normalize phone number (Standardizing for Rule 1 & Rule 5 consistency)
    to = normalize_wa_id(to)
    if not to:
         raise HTTPException(status_code=400, detail="Invalid phone number 'to'")

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

        res = send_whatsapp_message(db=db, to=to, organization_id=current_user.organization_id, media_path=str(file_path), media_type=media_type)

        # Check for Meta API errors
        if "error" in res:
            error_detail = res.get("error", "Failed to send media message")
            logger.error(f"Meta Media Send Error: To={to}, Type={media_type}, Error={error_detail}")
            raise HTTPException(status_code=400, detail=error_detail)

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

@router.get("/media/{media_id}")
async def get_media_proxy(
    media_id: str,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(get_current_user_flexible)
):
    """Proxy route to fetch media from Meta and serve it to the frontend."""
    # 0. Fetch Organization Credentials (Scoped to current user)
    from app.models.organization import OrganizationConfig
    config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == current_user.organization_id).first()
    if not config or not config.access_token:
        # Fallback to system settings
        from app.models.settings import SystemSettings
        settings = SystemSettings.get_settings(db)
        token = settings.whatsapp_token
    else:
        token = config.access_token

    if not token:
        raise HTTPException(status_code=400, detail="Meta Access Token is not configured")

    # 1. Get download URL from Meta
    meta_data = get_meta_media_url(media_id, token=token)
    download_url = meta_data.get("url")
    
    if not download_url:
        logger.error(f"Failed to get Meta media URL: {meta_data}")
        raise HTTPException(status_code=404, detail="Media not found on Meta")
        
    # 2. Get binary content
    content, mime_type = get_meta_media_content(download_url, token=token)
    
    if not content:
        raise HTTPException(status_code=404, detail="Failed to download media content")
        
    return Response(content=content, media_type=mime_type)
