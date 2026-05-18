from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.services.analytics_service import get_campaign_analytics, get_messaging_trends, get_dashboard_stats_service
from app.models.campaign import Campaign
from app.models.whatsapp_chat_model import WhatsAppMessage
import uuid
from app.core.security import get_current_user, user_has_bypass
from app.models.agent import Agent

# Access control workers
any_agent = get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard/stats")
def get_dashboard_stats(
    campaign_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Aggregate summary stats for the Dashboard page.
    """
    try:
        # Check if user is superadmin or belongs to the organization
        if org_id and not user_has_bypass(current_user):
            if str(current_user.organization_id) != org_id:
                raise HTTPException(status_code=403, detail="Forbidden: Cannot view other organization stats")
        
        return get_dashboard_stats_service(db, campaign_id, org_id)
    except Exception as e:
        import traceback
        print(f"ERROR calculating dashboard stats: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

@router.get("/campaign/{campaign_id}")
def get_campaign_stats(
    campaign_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Get aggregated delivery, read, and reply rates for a specific campaign.
    """
    try:
        # Isolation Check
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        if not user_has_bypass(current_user) and campaign.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Forbidden: Campaign belongs to another organization")

        stats = get_campaign_analytics(db, str(campaign_id))
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/trends")
def get_dashboard_trends(
    days: int = Query(7, ge=1, le=30),
    campaign_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Get message trends for the last X days.
    """
    try:
        # Check permission
        if org_id and not user_has_bypass(current_user):
            if str(current_user.organization_id) != org_id:
                raise HTTPException(status_code=403, detail="Forbidden")
        
        return get_messaging_trends(db, days, campaign_id, org_id)
    except Exception as e:
        print(f"ERROR calculating trends: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Trends error: {str(e)}")

@router.get("/dashboard/activity")
def get_dashboard_activity(
    limit: int = 5,
    hours: int = 24,
    campaign_id: Optional[str] = Query(None),
    org_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Get the most recent activities for the dashboard.
    """
    try:
        # Check permission
        if org_id and not user_has_bypass(current_user):
            if str(current_user.organization_id) != org_id:
                raise HTTPException(status_code=403, detail="Forbidden")
                
        from app.services.analytics_service import get_recent_activity
        return get_recent_activity(db, limit, hours, campaign_id, org_id)
    except Exception as e:
        print(f"ERROR fetching activity: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Activity error: {str(e)}")



