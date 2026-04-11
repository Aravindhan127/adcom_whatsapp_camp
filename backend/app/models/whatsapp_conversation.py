from sqlalchemy import Column, Integer, String, DateTime, Float, func, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"

    id = Column(Integer, primary_key=True, index=True)
    wa_id = Column(String(50), nullable=False, index=True)
    category = Column(String(20), nullable=False) # 'marketing', 'utility', 'authentication', 'service'
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    meta_message_id = Column(String(255), nullable=True)
    
    # Billing Status (Rule 1 & 3)
    billing_status = Column(String(20), default="pending") # 'pending', 'charged', 'failed'
    delivery_status = Column(String(20), default="sent")
    
    # Costs
    cost_usd = Column(Float, default=0.0)
    cost_inr = Column(Float, default=0.0)
    rate_usd = Column(Float, default=0.0)
    rate_inr = Column(Float, default=0.0)
    exchange_rate = Column(Float, default=84.0)

    # Cumulative stats (Rule 2)
    conversation_count = Column(Integer, default=0)
    cumulative_cost_usd = Column(Float, default=0.0)
    cumulative_cost_inr = Column(Float, default=0.0)

    # 24-hour window tracking
    last_user_reply_at = Column(DateTime(timezone=True), nullable=True)
    window_expires_at = Column(DateTime(timezone=True), nullable=True) # last_reply + 24h
    needs_agent = Column(Boolean, default=False)
    assigned_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id"), nullable=True)
    is_active = Column(Boolean, default=True)
