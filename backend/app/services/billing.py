from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import logger
import app.models  # Ensure all models (including Agent) are registered for FK lookups
from app.models.whatsapp_conversation import WhatsAppConversation
from app.models.settings import SystemSettings

def ensure_conversation(db: Session, wa_id: str, category: str, meta_message_id: str = None) -> Dict[str, Any]:
    """
    Ensures a 24-hour conversation window per category as per Meta rules.
    Also deducts the cost from the system balance if it's a new conversation.
    """
    print(f"Billing: Ensuring conversation for {wa_id} [{category}]")
    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    
    try:
        # Check if we already have an active conversation window for this category
        active = db.query(WhatsAppConversation).filter(
            WhatsAppConversation.wa_id == wa_id,
            WhatsAppConversation.category == category,
            WhatsAppConversation.started_at >= twenty_four_hours_ago
        ).order_by(WhatsAppConversation.started_at.desc()).first()
        
        if active:
            return {"conversation": active, "is_new": False, "cost_inr": 0.0}
    except Exception as e:
        logger.error(f"Billing: Error checking active conversation: {str(e)}")
        raise
    
    # NEW CONVERSATION: Calculate Billing
    settings = SystemSettings.get_settings(db)
    exchange_rate = settings.exchange_rate or 84.0
    
    # 1000 Free Service Conversations check
    if category.lower() == "service":
        try:
            first_of_month = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            service_count = db.query(WhatsAppConversation).filter(
                WhatsAppConversation.category == "service",
                WhatsAppConversation.started_at >= first_of_month
            ).count()
            
            if service_count < 1000:
                cost_inr = 0.0
                cost_usd = 0.0
            else:
                cost_inr = settings.service_rate_inr or 0.0
                cost_usd = cost_inr / exchange_rate
        except Exception as e:
            logger.error(f"Billing: Error calculating service cost: {str(e)}")
            cost_inr = 0.0
            cost_usd = 0.0
    else:
        rates = {
            "marketing": settings.marketing_rate_inr,
            "utility": settings.utility_rate_inr,
            "authentication": settings.authentication_rate_inr,
        }
        cost_inr = rates.get(category.lower())
        if cost_inr is None:
             cost_inr = 0.82
        
        cost_usd = cost_inr / exchange_rate
    
    # Create the conversation
    try:
        new_conv = WhatsAppConversation(
            wa_id=wa_id,
            category=category,
            cost_usd=cost_usd,
            cost_inr=cost_inr,
            rate_inr=cost_inr,
            exchange_rate=exchange_rate,
            started_at=datetime.now(timezone.utc),
            billing_status="charged",
            meta_message_id=meta_message_id
        )
        
        # Deduct from System Balance (Rule 3)
        if cost_inr > 0:
            settings.meta_balance_inr = (settings.meta_balance_inr or 0) - cost_inr
            settings.meta_balance_usd = (settings.meta_balance_usd or 0) - cost_usd
        
        db.add(new_conv)
        db.commit()
        db.refresh(new_conv)
        
        return {"conversation": new_conv, "is_new": True, "cost_inr": cost_inr, "cost_usd": cost_usd}
    except Exception as e:
        logger.error(f"Billing: Error saving new conversation: {str(e)}")
        db.rollback()
        raise
