from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.models.campaign_run import CampaignRun
from app.models.whatsapp_chat_model import WhatsAppMessage
from app.models.settings import SystemSettings
from app.models.campaign import Campaign
from app.models.contact import Contact
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from typing import Dict, List, Optional
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

def _get_period_stats(db: Session, start: datetime, end: datetime, campaign_id: Optional[str] = None, org_id: Optional[str] = None) -> Dict:
    """Helper to fetch stats for a specific timeframe."""
    query = db.query(WhatsAppMessage).join(
        Campaign, WhatsAppMessage.campaign_id == Campaign.id
    ).filter(
        Campaign.is_deleted == False,
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= start,
        WhatsAppMessage.created_at < end
    )
    
    if campaign_id:
        query = query.filter(WhatsAppMessage.campaign_id == campaign_id)
    if org_id:
        query = query.filter(Campaign.organization_id == org_id)
        
    msgs = query.all()
    
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

def get_dashboard_stats_service(db: Session, campaign_id: Optional[str] = None, org_id: Optional[str] = None) -> Dict:
    """
    Aggregate overall dashboard statistics for the professional UI.
    Now includes 24h vs Previous 24h trend calculations.
    """
    now = datetime.now(timezone.utc)
    t24h = now - timedelta(hours=24)
    t48h = now - timedelta(hours=48)

    # 1. Overall Totals
    query = db.query(WhatsAppMessage).join(
        Campaign, WhatsAppMessage.campaign_id == Campaign.id
    ).filter(
        Campaign.is_deleted == False,
        WhatsAppMessage.direction == "out"
    )
    if campaign_id:
        query = query.filter(WhatsAppMessage.campaign_id == campaign_id)
    if org_id:
        query = query.filter(Campaign.organization_id == org_id)
        
    total = query.count()
    delivered = query.filter(WhatsAppMessage.delivery_status.in_(["delivered", "read"])).count()
    read = query.filter(WhatsAppMessage.delivery_status == "read").count()
    failed = query.filter(WhatsAppMessage.delivery_status == "failed").count()
    
    # Rule: Total spend calculation must include both WhatsApp business costs and AI integration costs
    spend_query = db.query(
        func.sum(
            func.coalesce(WhatsAppMessage.llm_cost_inr, 0.0) + 
            func.coalesce(WhatsAppMessage.whatsapp_cost, 0.0)
        )
    ).join(
        Campaign, WhatsAppMessage.campaign_id == Campaign.id
    ).filter(
        Campaign.is_deleted == False,
        WhatsAppMessage.direction == "out"
    )
    
    if campaign_id:
        spend_query = spend_query.filter(WhatsAppMessage.campaign_id == campaign_id)
        
    total_spend_inr = spend_query.scalar() or 0.0

    # 2. Period Comparisons (Last 24h vs Previous 24h)
    curr = _get_period_stats(db, t24h, now, campaign_id, org_id)
    prev = _get_period_stats(db, t48h, t24h, campaign_id, org_id)

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
    # Note: For impersonation, we might want to return org-specific balance if implemented, 
    # but currently balance is global in SystemSettings.
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

def get_messaging_trends(db: Session, days: int = 7, campaign_id: Optional[str] = None, org_id: Optional[str] = None) -> List[Dict]:
    """
    Get message counts (sent, delivered, read) grouped by day.
    """
    end_date = datetime.now(timezone.utc)  # BE-FIX BE-13: deprecated utcnow() replaced
    start_date = end_date - timedelta(days=days-1)
    
    # Query for daily aggregates
    query = db.query(
        func.date(WhatsAppMessage.created_at).label('date'),
        func.count(WhatsAppMessage.id).label('sent'),
        func.sum(case((WhatsAppMessage.delivery_status.in_(["delivered", "read"]), 1), else_=0)).label('delivered'),
        func.sum(case((WhatsAppMessage.delivery_status == "read", 1), else_=0)).label('read')
    ).join(
        Campaign, WhatsAppMessage.campaign_id == Campaign.id
    ).filter(
        Campaign.is_deleted == False,
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= start_date
    )
    
    if campaign_id:
        query = query.filter(WhatsAppMessage.campaign_id == campaign_id)
    if org_id:
        query = query.filter(Campaign.organization_id == org_id)
        
    stats = query.group_by(
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

def get_recent_activity(db: Session, limit: int = 5, hours: int = 24, campaign_id: Optional[str] = None, org_id: Optional[str] = None) -> List[Dict]:
    """
    Get the most recent outbound messages for the activity feed.
    Defaults to last 24 hours.
    """
    # Join with Campaign to get the campaign name and Contact to get contact names
    query = db.query(WhatsAppMessage, Campaign.name, Contact.name).join(
        Campaign, (WhatsAppMessage.campaign_id == Campaign.id)
    ).outerjoin(
        Contact, func.right(WhatsAppMessage.wa_id, 10) == func.right(Contact.phone_number, 10)
    ).filter(
        Campaign.is_deleted == False
    )
    
    if hours > 0:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        query = query.filter(WhatsAppMessage.created_at >= since)
        
    if campaign_id:
        query = query.filter(WhatsAppMessage.campaign_id == campaign_id)
    if org_id:
        query = query.filter(Campaign.organization_id == org_id)
        
    results_raw = query.order_by(
        WhatsAppMessage.created_at.desc()
    ).limit(limit).all()
    
    results = []
    now_utc = datetime.now(timezone.utc)
    
    for m, campaign_name, contact_name in results_raw:
        # Map statuses to colors for the UI
        color = "indigo"
        status_label = m.delivery_status.upper() if m.delivery_status else "SENT"
        
        if m.delivery_status == "read": color = "indigo"
        elif m.delivery_status == "delivered": color = "emerald"
        elif m.delivery_status == "failed": color = "rose"
        elif m.delivery_status == "pending": color = "amber"

        # BE-FIX: Correct timezone handling for "time ago" string
        # m.created_at is timezone-aware (IST in our case). 
        # Convert to UTC to compare with now_utc.
        m_utc = m.created_at.astimezone(timezone.utc)
        diff = now_utc - m_utc
        
        total_seconds = int(diff.total_seconds())
        
        if total_seconds < 0:
            time_str = "Just now" # Future time due to clock drift
        elif total_seconds < 60:
            time_str = "Just now"
        elif total_seconds < 3600:
            time_str = f"{total_seconds // 60}m ago"
        elif total_seconds < 86400:
            time_str = f"{total_seconds // 3600}h ago"
        else:
            time_str = f"{total_seconds // 86400}d ago"

        # Add exact clock time (formatted in local time stored in DB)
        exact_time = m.created_at.strftime("%I:%M %p")

        results.append({
            "user": m.wa_id,
            "user_name": contact_name or m.wa_id,
            "campaign": campaign_name or "Direct",
            "msg": m.template_name or "Direct Message",
            "time": time_str,
            "exact_time": exact_time,
            "status": status_label,
            "color": color
        })
    return results

def get_campaign_detailed_logs(db: Session, campaign_id: str, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> Dict:
    """
    Get all message statuses for a specific campaign, joined with contact names.
    Supports status filtering (e.g., 'sent', 'delivered', 'read', 'failed').
    """
    from app.models.contact import Contact
    
    query = db.query(
        WhatsAppMessage.wa_id,
        WhatsAppMessage.delivery_status,
        WhatsAppMessage.status_error,
        WhatsAppMessage.created_at,
        Contact.name.label("contact_name")
    ).outerjoin(
        Contact, func.right(WhatsAppMessage.wa_id, 10) == func.right(Contact.phone_number, 10)
    ).filter(
        WhatsAppMessage.campaign_id == campaign_id,
        WhatsAppMessage.direction == "out"
    )

    if status and status.lower() != 'all':
        query = query.filter(WhatsAppMessage.delivery_status == status.lower())
    
    total = query.count()
    items_raw = query.order_by(WhatsAppMessage.created_at.desc()).offset(skip).limit(limit).all()
    
    items = []
    for row in items_raw:
        items.append({
            "phone": row.wa_id,
            "name": row.contact_name or "Unknown",
            "status": row.delivery_status or "sent",
            "error": row.status_error,
            "timestamp": row.created_at.isoformat()
        })
        
    return {
        "total": total,
        "items": items
    }

def export_campaign_logs_to_excel(db: Session, campaign_id: str, status: Optional[str] = None) -> io.BytesIO:
    """
    Export filtered campaign logs to an Excel file.
    """
    from app.models.contact import Contact
    from app.models.campaign import Campaign

    # Get campaign name
    campaign = db.query(Campaign).get(campaign_id)
    campaign_name = campaign.name if campaign else "Campaign"

    # Query all logs (no limit for export)
    query = db.query(
        WhatsAppMessage.wa_id,
        WhatsAppMessage.delivery_status,
        WhatsAppMessage.status_error,
        WhatsAppMessage.created_at,
        Contact.name.label("contact_name")
    ).outerjoin(
        Contact, func.right(WhatsAppMessage.wa_id, 10) == func.right(Contact.phone_number, 10)
    ).filter(
        WhatsAppMessage.campaign_id == campaign_id,
        WhatsAppMessage.direction == "out"
    )

    if status and status.lower() != 'all':
        query = query.filter(WhatsAppMessage.delivery_status == status.lower())
    
    logs = query.order_by(WhatsAppMessage.created_at.desc()).all()

    # Create Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Recipient Logs"

    # Header
    headers = ["Name", "Phone Number", "Status", "Time", "Error Details"]
    ws.append(headers)

    # Style Header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4F46E5", end_color="4F46E5", fill_type="solid") # Indigo-600
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill

    # Data
    for log in logs:
        ws.append([
            log.contact_name or "Unknown",
            log.wa_id,
            (log.delivery_status or "sent").upper(),
            log.created_at.strftime("%Y-%m-%d %I:%M %p"),
            log.status_error or ""
        ])

    # Auto-adjust column width
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except: pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width

    # Save to buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

