import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey, JSON, Boolean

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    template_name = Column(String(255), nullable=False) # Maps to Meta Template Name
    status = Column(String(20), default="draft") # 'draft', 'scheduled', 'running', 'completed', 'failed'
    is_deleted = Column(Boolean, default=False)
    media_url = Column(Text, nullable=True) # Public URL for Image/Video/Doc header
    template_params = Column(JSON, nullable=True) # Mapping of variable ID to contact field or static text

    
    # Links
    contact_list_id = Column(UUID(as_uuid=True), ForeignKey("contact_lists.id"), nullable=False)
    
    # Analytics / Tracking
    total_contacts = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    read_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    on_hold_count = Column(Integer, default=0)
    failure_reason = Column(String(255), nullable=True) # e.g. 'Meta Rate Limit', 'Quality Risk'
    total_cost_inr = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
