import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import enum

class ResponseType(str, enum.Enum):
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    REMIND_LATER = "REMIND_LATER"
    STOP_OFFERS = "STOP_OFFERS"

class EngagementEvent(Base):
    __tablename__ = "engagement_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wa_id = Column(String(50), nullable=False, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True)
    response_type = Column(String(20), nullable=False)
    button_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wa_id = Column(String(50), nullable=False, unique=True, index=True)
    last_response_type = Column(String(20), nullable=True)
    last_campaign_id = Column(UUID(as_uuid=True), nullable=True)
    response_count = Column(Integer, default=0)
    last_response_at = Column(DateTime(timezone=True), onupdate=func.now())
    suppressed_until = Column(DateTime(timezone=True), nullable=True)
    is_high_engagement = Column(Column(Integer, default=0)) # 0 or 1
    created_at = Column(DateTime(timezone=True), server_default=func.now())
