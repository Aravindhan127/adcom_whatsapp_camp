from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.whatsapp_chat_model import WhatsAppMessage
from datetime import datetime, timedelta, timezone

# Meta Tiers: 1k, 10k, 100k, Unlimited
DEFAULT_MAX_DAILY_LIMIT = 1000

def get_daily_sent_count(db: Session) -> int:
    """
    Get total outgoing messages sent in the last 24 hours.
    """
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return db.query(WhatsAppMessage).filter(
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= yesterday
    ).count()

def is_within_limits(db: Session, threshold: int = DEFAULT_MAX_DAILY_LIMIT) -> bool:
    """
    Check if we are close to hitting the daily limit for the current tier.
    """
    count = get_daily_sent_count(db)
    return count < threshold

def check_quality_risk(db: Session) -> float:
    """
    Calculate the failure rate of messages sent in the last 24 hours.
    High failure/rejection rates risk number bans.
    """
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    last_msgs = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= yesterday
    ).order_by(WhatsAppMessage.created_at.desc()).limit(100).all()

    if not last_msgs:
        return 0.0

    failed = sum(1 for m in last_msgs if m.delivery_status == "failed")
    return (failed / len(last_msgs)) * 100
