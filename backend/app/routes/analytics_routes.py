from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.services.analytics_service import get_campaign_analytics, get_messaging_trends, get_dashboard_stats_service
from app.models.campaign import Campaign
from app.models.whatsapp_chat_model import WhatsAppMessage
import uuid
from app.core.security import get_current_user
from app.models.agent import Agent

# Access control workers
any_agent = get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Aggregate summary stats for the Dashboard page.
    """
    try:
        return get_dashboard_stats_service(db)
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
        stats = get_campaign_analytics(db, str(campaign_id))
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/trends")
def get_dashboard_trends(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Get message trends for the last X days.
    """
    try:
        return get_messaging_trends(db, days)
    except Exception as e:
        print(f"ERROR calculating trends: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Trends error: {str(e)}")

@router.get("/dashboard/activity")
def get_dashboard_activity(
    limit: int = 5,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    """
    Get the most recent activities for the dashboard.
    """
    try:
        from app.services.analytics_service import get_recent_activity
        return get_recent_activity(db, limit)
    except Exception as e:
        print(f"ERROR fetching activity: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Activity error: {str(e)}")

