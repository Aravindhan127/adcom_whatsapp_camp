from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

# Note: WhatsAppConversation import removed to avoid circular dependency
# The ForeignKey reference still works via SQLAlchemy's declarative system

class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    wa_id = Column(String(50), nullable=False, index=True)  # Receiver phone
    direction = Column(String(10), nullable=False)           # 'in' or 'out'
    message = Column(Text, nullable=True)
    media_url = Column(Text, nullable=True)
    media_id = Column(String(255), nullable=True)            # Reusable Meta Media ID
    message_type = Column(String(20), default="text")        # 'text', 'image', 'document', 'template'

    # Meta specific
    # BE-FIX BE-17: REMOVED unique=True — duplicate error codes for same phone + different campaigns
    # caused DB IntegrityError crashing the entire batch. Non-unique index still fast for lookups.
    meta_message_id = Column(String(255), nullable=True, index=True)
    delivery_status = Column(String(20), default="sent")     # 'sent', 'delivered', 'read', 'failed'
    status_error = Column(Text, nullable=True)
    template_name = Column(String(255), nullable=True)

    # Financial & AI Tracking
    conversation_id = Column(Integer, ForeignKey("whatsapp_conversations.id"), nullable=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    llm_cost_usd = Column(Float, default=0.0)
    llm_cost_inr = Column(Float, default=0.0)
    whatsapp_cost = Column(Float, default=0.0)  # Cost for this specific message window

    created_at = Column(DateTime(timezone=True), server_default=func.now())
