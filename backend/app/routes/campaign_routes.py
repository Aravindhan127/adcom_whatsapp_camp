import uuid
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db, logger
import traceback
import tempfile
import os

from app.models.campaign import Campaign
from app.models.contact import ContactList
from app.models.settings import SystemSettings
from app.services.campaign_service import start_campaign_run, pause_campaign, resume_campaign
from app.services.analytics_service import get_campaign_analytics, get_campaign_detailed_logs
from app.services.meta_api import upload_media
from app.core.security import get_current_user, RoleChecker
from app.models.agent import Agent
from app.models.contact import Contact, ContactList
from app.models.template import WhatsAppTemplate
from app.services.audit_service import log_action
from fastapi import Request

# Access control workers
admin_only = RoleChecker(["admin"])
any_agent = get_current_user

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.post("/upload-media", summary="Upload Campaign Media to Meta")
async def upload_campaign_media(
    file: UploadFile = File(...),
    current_user: Agent = Depends(any_agent)
):
    """
    Uploads a media file (Image/Video/Doc) to Meta's /media endpoint.
    Returns the Meta Media ID required for sending template headers.
    """
    try:
        content = await file.read()
        fd, temp_path = tempfile.mkstemp()
        try:
            with open(fd, 'wb') as f:
                f.write(content)
            
            # Send file to Meta API
            # Sanitize content_type (e.g., 'video/mp4' -> 'video')
            m_type = "image"
            if file.content_type:
                if "video" in file.content_type: m_type = "video"
                elif "audio" in file.content_type: m_type = "audio"
                elif "pdf" in file.content_type or "document" in file.content_type: m_type = "document"

            res = upload_media(temp_path, m_type)
            if "error" in res:
                raise HTTPException(status_code=400, detail=res["error"])
            
            # Return either 'id' or fallback to the whole response
            media_id = res.get("id")
            if not media_id:
                raise HTTPException(status_code=400, detail="Meta did not return a media ID")
            
            return {"id": media_id}
            
        finally:
            os.remove(temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CampaignCreate(BaseModel):
    name: str
    template_name: str
    contact_list_id: Optional[uuid.UUID] = None
    contact_ids: Optional[List[uuid.UUID]] = None
    scheduled_at: Optional[datetime] = None
    media_url: Optional[str] = None
    template_params: Optional[dict] = None



class CampaignResponse(BaseModel):
    id: uuid.UUID
    name: str
    template_name: str
    status: str
    total_contacts: int
    sent_count: int
    delivered_count: int
    read_count: int
    failed_count: int
    on_hold_count: int = 0
    failure_reason: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("/", summary="Create a Campaign", response_model=CampaignResponse)
def create_campaign(
    payload: CampaignCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    final_list_id = payload.contact_list_id

    # If contact_ids are provided, create a special list for this campaign
    if payload.contact_ids:
        new_list = ContactList(
            name=f"List for {payload.name} ({datetime.now().strftime('%H%M%S')})",
            description=f"Auto-generated for campaign {payload.name}"
        )
        db.add(new_list)
        db.commit()
        db.refresh(new_list)
        final_list_id = new_list.id
        
        # Link contacts
        db.query(Contact).filter(Contact.id.in_(payload.contact_ids)).update(
            {"list_id": final_list_id}, synchronize_session=False
        )
        db.commit()

    if not final_list_id:
        raise HTTPException(status_code=400, detail="Either contact_list_id or contact_ids must be provided")

    # Ensure contact list exists
    contact_list = db.query(ContactList).get(final_list_id)
    if not contact_list:
        raise HTTPException(status_code=404, detail="Contact list not found")

    media_url = payload.media_url
    template_params = payload.template_params

    # Auto-populate from Template if not provided in Campaign
    if not media_url or not template_params:
        template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == payload.template_name).first()
        if template:
            if not media_url and template.media_id:
                media_url = template.media_id
            if not template_params and template.variable_mappings:
                template_params = template.variable_mappings

    total_contacts = db.query(Contact).filter(
        Contact.list_id == final_list_id
    ).count()

    new_campaign = Campaign(
        name=payload.name,
        template_name=payload.template_name,
        contact_list_id=final_list_id,
        status="draft",
        media_url=media_url,
        template_params=template_params,
        scheduled_at=payload.scheduled_at,
        total_contacts=total_contacts
    )
    db.add(new_campaign)
    db.commit()
    db.refresh(new_campaign)

    log_action(
        db, "CREATE_CAMPAIGN", "CAMPAIGNS", 
        user_id=str(current_user.id), username=current_user.username,
        details={"campaign_id": str(new_campaign.id), "name": new_campaign.name},
        request=request
    )

    return new_campaign


@router.get("/", summary="List All Campaigns")
def list_campaigns(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    query = db.query(Campaign).filter(Campaign.is_deleted == False)
    if search:
        query = query.filter(Campaign.name.ilike(f"%{search}%"))
    if status:
        query = query.filter(Campaign.status == status)
    
    total = query.count()
    
    # Sorting
    valid_columns = {
        "name": Campaign.name,
        "status": Campaign.status,
        "template_name": Campaign.template_name,
        "created_at": Campaign.created_at,
        "sent_count": Campaign.sent_count
    }
    
    target_col_name = sort_by if sort_by in valid_columns else "created_at"
    sort_col = valid_columns[target_col_name]
    
    if sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    items = query.offset(skip).limit(limit).all()
    
    # Enrich with real-time stats (Rule: Always show correct data)
    enriched_items = []
    for c in items:
        # We manually map stats from WhatsAppMessage logs to the Campaign object
        # for real-time accuracy in the UI list view
        analytics = get_campaign_analytics(db, str(c.id))
        c.sent_count = analytics.get("total_sent", 0)
        c.delivered_count = analytics.get("delivered", 0)
        c.read_count = analytics.get("read", 0)
        c.failed_count = analytics.get("failed", 0)
        # Note: We do NOT commit these changes to the DB here to avoid stale data persistence
        enriched_items.append(c)

    return {
        "total": total,
        "items": enriched_items,
        "limit": limit,
        "skip": skip
    }


@router.get("/{campaign_id}", summary="Get Campaign Detail", response_model=CampaignResponse)
def get_campaign(
    campaign_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign or campaign.is_deleted:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.post("/{campaign_id}/start", summary="Start or Schedule a Campaign")
def start_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(get_current_user)
):
    logger.info(f"Campaign start requested by user: {current_user.username}")
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if campaign.status not in ("draft", "scheduled", "on_hold"):
        raise HTTPException(status_code=400, detail=f"Cannot start campaign with status '{campaign.status}'")

    result = start_campaign_run(db, campaign_id, scheduled_at=campaign.scheduled_at)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    log_action(
        db, "START_CAMPAIGN", "CAMPAIGNS", 
        user_id=str(current_user.id), username=current_user.username,
        details={"campaign_id": str(campaign_id), "name": campaign.name},
        request=request
    )

    return result


@router.post("/{campaign_id}/pause", summary="Pause a running campaign")
def pause_campaign_route(
    campaign_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(get_current_user)
):
    result = pause_campaign(db, campaign_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    log_action(
        db, "PAUSE_CAMPAIGN", "CAMPAIGNS", 
        user_id=str(current_user.id), username=current_user.username,
        details={"campaign_id": str(campaign_id)},
        request=request
    )
    return result


@router.post("/{campaign_id}/resume", summary="Resume a paused campaign")
def resume_campaign_route(
    campaign_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(get_current_user)
):
    result = resume_campaign(db, campaign_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    log_action(
        db, "RESUME_CAMPAIGN", "CAMPAIGNS", 
        user_id=str(current_user.id), username=current_user.username,
        details={"campaign_id": str(campaign_id)},
        request=request
    )
    return result


@router.get("/{campaign_id}/stats", summary="Get Campaign Analytics")
def get_campaign_stats(
    campaign_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    analytics = get_campaign_analytics(db, str(campaign_id))
    return {
        **analytics, 
        "campaign": {
            "id": str(campaign.id), 
            "name": campaign.name, 
            "status": campaign.status,
            "on_hold_count": campaign.on_hold_count,
            "failure_reason": campaign.failure_reason,
        }
    }


@router.get("/{campaign_id}/logs", summary="Get Granular Campaign Logs")
def get_campaign_logs_route(
    campaign_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Returns a list of all recipients and their current message status for this campaign.
    """
    return get_campaign_detailed_logs(db, str(campaign_id), skip=skip, limit=limit)


# BE-FIX BE-15: These specific routes MUST come BEFORE /{campaign_id} to avoid
# FastAPI treating 'active' and 'system' as UUID path parameters (returns 422).

@router.get("/active/progress", summary="Get Live Progress of Running Campaigns")
def get_active_campaigns_progress(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Get progress of all currently running campaigns for global status bar.
    This route MUST be registered before /{campaign_id} to avoid 422 errors.
    """
    logger.info("CampaignRoutes: Fetching active campaigns progress")
    active_campaigns = db.query(Campaign).filter(Campaign.status == "running", Campaign.is_deleted == False).all()
    results = []
    for c in active_campaigns:
        analytics = get_campaign_analytics(db, str(c.id))
        sent = analytics.get("total_sent", 0)
        total = c.total_contacts or 0
        progress = round((sent / total * 100), 1) if total > 0 else 0
        results.append({
            "id": str(c.id),
            "name": c.name,
            "progress": progress,
            "sent": sent,
            "total": total
        })
    return results


@router.get("/system/balance", summary="Get Meta Balance & Settings")
def get_system_balance(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    logger.info("CampaignRoutes: Fetching system balance")
    settings = SystemSettings.get_settings(db)
    return settings


@router.post("/system/balance", summary="Update Meta Balance (Recharge)")
def update_system_balance(
    amount: float,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Recharge amount must be positive")
    settings = SystemSettings.get_settings(db)
    rate = settings.exchange_rate or 84.0
    settings.meta_balance_inr += amount
    settings.meta_balance_usd += round(amount / rate, 2)
    db.commit()
    db.refresh(settings)
    logger.info(f"CampaignRoutes: Balance updated by ₹{amount}. New balance: ₹{settings.meta_balance_inr}")
    
    log_action(
        db, "UPDATE_BALANCE", "SYSTEM", 
        user_id=str(current_user.id), username=current_user.username,
        details={"recharge_amount": amount, "new_balance": settings.meta_balance_inr},
        request=request
    )

    return {"message": "Balance updated", "new_balance": settings.meta_balance_inr}


@router.delete("/{campaign_id}", summary="Delete a Campaign")
def delete_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    logger.info(f"CampaignRoutes: Soft deleting campaign {campaign_id} (status={campaign.status}) by {current_user.username}")
    campaign.is_deleted = True
    db.commit()

    log_action(
        db, "DELETE_CAMPAIGN", "CAMPAIGNS", 
        user_id=str(current_user.id), username=current_user.username,
        details={"campaign_id": str(campaign_id), "name": campaign.name},
        request=request
    )

    return {"message": "Campaign deleted"}
