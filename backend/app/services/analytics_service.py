from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.models.campaign_run import CampaignRun
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.settings import SystemSettings
from typing import Dict, List
from datetime import datetime, timezone, timedelta

def get_campaign_analytics(db: Session, campaign_id: str) -> Dict:
    """
    Aggregate delivery, read, and reply rates for a specific campaign.
    """
    total_sent = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.campaign_id == campaign_id,
        WhatsAppMessage.direction == "out"
    ).count()
    
    # Rule: Success Rate (delivered) must include "read" status
    delivered = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.campaign_id == campaign_id,
        WhatsAppMessage.delivery_status.in_(["delivered", "read"])
    ).count()
    
    read = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.campaign_id == campaign_id,
        WhatsAppMessage.delivery_status == "read"
    ).count()

    failed = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.campaign_id == campaign_id,
        WhatsAppMessage.delivery_status == "failed"
    ).count()
    
    return {
        "total_sent": total_sent,
        "delivered": delivered,
        "read": read,
        "failed": failed,
        "delivery_rate": (delivered / total_sent * 100) if total_sent > 0 else 0,
        "read_rate": (read / total_sent * 100) if total_sent > 0 else 0
    }

def _get_period_stats(db: Session, start: datetime, end: datetime) -> Dict:
    """Helper to fetch stats for a specific timeframe."""
    msgs = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= start,
        WhatsAppMessage.created_at < end
    ).all()
    
    total = len(msgs)
    delivered = sum(1 for m in msgs if m.delivery_status in ["delivered", "read"])
    read = sum(1 for m in msgs if m.delivery_status == "read")
    # Rule: Total spend is the sum of LLM cost and WhatsApp Conversation cost
    spend = sum((m.llm_cost_inr or 0.0) + (m.whatsapp_cost or 0.0) for m in msgs)
    
    return {
        "total": total,
        "delivered": delivered,
        "read": read,
        "spend": spend,
        "delivery_rate": (delivered / total * 100) if total > 0 else 0,
        "read_rate": (read / delivered * 100) if delivered > 0 else 0
    }

def get_dashboard_stats_service(db: Session) -> Dict:
    """
    Aggregate overall dashboard statistics for the professional UI.
    Now includes 24h vs Previous 24h trend calculations.
    """
    now = datetime.now(timezone.utc)
    t24h = now - timedelta(hours=24)
    t48h = now - timedelta(hours=48)

    # 1. Overall Totals
    total = db.query(WhatsAppMessage).filter(WhatsAppMessage.direction == "out").count()
    delivered = db.query(WhatsAppMessage).filter(WhatsAppMessage.delivery_status.in_(["delivered", "read"])).count()
    read = db.query(WhatsAppMessage).filter(WhatsAppMessage.delivery_status == "read").count()
    failed = db.query(WhatsAppMessage).filter(WhatsAppMessage.delivery_status == "failed").count()
    
    # Rule: Total spend calculation must include both WhatsApp business costs and AI integration costs
    total_spend_inr = db.query(
        func.sum(
            func.coalesce(WhatsAppMessage.llm_cost_inr, 0.0) + 
            func.coalesce(WhatsAppMessage.whatsapp_cost, 0.0)
        )
    ).scalar() or 0.0

    # 2. Period Comparisons (Last 24h vs Previous 24h)
    curr = _get_period_stats(db, t24h, now)
    prev = _get_period_stats(db, t48h, t24h)

    def calc_trend(current, previous):
        if previous == 0: return 0.0 if current == 0 else 100.0
        return ((current - previous) / previous) * 100

    trends = {
        "total": calc_trend(curr['total'], prev['total']),
        "delivery_rate": curr['delivery_rate'] - prev['delivery_rate'], # Change in percentage points
        "read_rate": curr['read_rate'] - prev['read_rate'],
        "spend": calc_trend(curr['spend'], prev['spend'])
    }

    # 3. System Balance
    settings = SystemSettings.get_settings(db)
    
    return {
        "messages": {
            "total": total,
            "delivered": delivered,
            "read": read,
            "failed": failed,
            "trend": round(trends['total'], 1)
        },
        "rates": {
            "delivery_trend": round(trends['delivery_rate'], 1),
            "read_trend": round(trends['read_rate'], 1)
        },
        "costs": {
            "total_usd": total_spend_inr / (settings.exchange_rate or 84.0),
            "total_inr": total_spend_inr,
            "trend_inr": round(trends['spend'], 1)
        },
        "balance": {
            "estimated_inr": settings.meta_balance_inr or 0.0,
            "estimated_usd": settings.meta_balance_usd or 0.0
        },
        "brochures": {
            "sent": db.query(WhatsAppMessage).filter(WhatsAppMessage.message_type == "document").count() 
        }
    }

def get_messaging_trends(db: Session, days: int = 7) -> List[Dict]:
    """
    Get message counts (sent, delivered, read) grouped by day.
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days-1)
    
    # Query for daily aggregates
    stats = db.query(
        func.date(WhatsAppMessage.created_at).label('date'),
        func.count(WhatsAppMessage.id).label('sent'),
        func.sum(case((WhatsAppMessage.delivery_status.in_(["delivered", "read"]), 1), else_=0)).label('delivered'),
        func.sum(case((WhatsAppMessage.delivery_status == "read", 1), else_=0)).label('read')
    ).filter(
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= start_date
    ).group_by(
        func.date(WhatsAppMessage.created_at)
    ).order_by(
        func.date(WhatsAppMessage.created_at)
    ).all()

    # Fill in missing dates to ensure a continuous line
    results = []
    stats_map = {str(s.date): s for s in stats}
    
    for i in range(days):
        current_date = (start_date + timedelta(days=i)).date()
        date_str = str(current_date)
        
        stat = stats_map.get(date_str)
        results.append({
            "date": date_str,
            "name": current_date.strftime("%b %d"),
            "sent": int(stat.sent) if stat else 0,
            "delivered": int(stat.delivered) if stat and stat.delivered else 0,
            "read": int(stat.read) if stat and stat.read else 0
        })
        
    return results

def get_recent_activity(db: Session, limit: int = 5) -> List[Dict]:
    """
    Get the most recent outbound messages for the activity feed.
    """
    messages = db.query(WhatsAppMessage).order_by(
        WhatsAppMessage.created_at.desc()
    ).limit(limit).all()
    
    results = []
    for m in messages:
        # Map statuses to colors for the UI
        color = "indigo"
        status_label = m.delivery_status.upper() if m.delivery_status else "SENT"
        
        if m.delivery_status == "read": color = "indigo"
        elif m.delivery_status == "delivered": color = "emerald"
        elif m.delivery_status == "failed": color = "rose"
        elif m.delivery_status == "pending": color = "amber"

        # Format time ago (rough)
        diff = datetime.utcnow() - m.created_at.replace(tzinfo=None)
        if diff.seconds < 60: time_str = "Just now"
        elif diff.seconds < 3600: time_str = f"{diff.seconds // 60}m ago"
        elif diff.days < 1: time_str = f"{diff.seconds // 3600}h ago"
        else: time_str = f"{diff.days}d ago"

        results.append({
            "user": m.wa_id,
            "msg": m.template_name or "Direct Message",
            "time": time_str,
            "status": status_label,
            "color": color
        })
    return results
