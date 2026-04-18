from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.whatsapp_chat_model import WhatsAppMessage
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger("adcom-api")

# Meta Tiers: 1k, 10k, 100k, Unlimited
DEFAULT_MAX_DAILY_LIMIT = 1000

def get_daily_sent_count(db: Session) -> int:
    """
    Get total SUCCESSFULLY SENT outgoing messages in the last 24 hours.
    BE-FIX BE-14: Excludes 'failed' status — failed messages don't consume Meta quota.
    """
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    count = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= yesterday,
        WhatsAppMessage.delivery_status != "failed"  # BE-FIX: only count real sends
    ).count()
    logger.debug(f"RestrictionService: Daily sent count (non-failed, last 24h) = {count}")
    return count

def is_within_limits(db: Session, threshold: int = DEFAULT_MAX_DAILY_LIMIT) -> bool:
    """
    Check if we are under the daily limit for the current tier.
    """
    count = get_daily_sent_count(db)
    within = count < threshold
    if not within:
        logger.warning(f"RestrictionService: Daily limit REACHED ({count}/{threshold}). New sends will be blocked.")
    return within

def check_quality_risk(db: Session) -> float:
    """
    Calculate the failure rate of messages sent in the last 24 hours.
    High failure/rejection rates risk number bans.
    BE-FIX BE-8: Excludes LOCAL failures (invalid phone format) from quality risk calculation.
    Only Meta-rejected messages (those with a real meta_message_id) count as quality failures.
    """
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    last_msgs = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.direction == "out",
        WhatsAppMessage.created_at >= yesterday,
        # BE-FIX: Only count messages that actually reached Meta (have meta_message_id or are not LOCAL errors)
        ~WhatsAppMessage.meta_message_id.like("LOCAL_%")
    ).order_by(WhatsAppMessage.created_at.desc()).limit(100).all()

    if not last_msgs:
        logger.debug("RestrictionService: Quality risk check — no recent messages found.")
        return 0.0

    failed = sum(1 for m in last_msgs if m.delivery_status == "failed")
    risk = (failed / len(last_msgs)) * 100
    logger.debug(f"RestrictionService: Quality risk = {risk:.1f}% ({failed} failed out of {len(last_msgs)} recent messages)")
    return risk
