import uuid
from sqlalchemy import Column, String, DateTime, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class CampaignRun(Base):
    __tablename__ = "campaign_runs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False)
    status = Column(String(20), default="pending") # 'pending', 'running', 'completed', 'failed', 'paused'
    
    total_contacts = Column(Integer, default=0)
    processed_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    on_hold_count = Column(Integer, default=0)
    total_cost_inr = Column(Float, default=0.0)
    total_cost_usd = Column(Float, default=0.0)
    
    last_processed_offset = Column(Integer, default=0) # Resume mechanism
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    on_hold_since = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
