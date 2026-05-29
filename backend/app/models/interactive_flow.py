import uuid
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class InteractiveFlow(Base):
    __tablename__ = "interactive_flows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    trigger_keyword = Column(String(255), index=True, nullable=False)  # matches button ID/payload or keyword text
    response_type = Column(String(50), nullable=False)  # 'text' or 'template'
    response_text = Column(Text, nullable=True)
    response_template = Column(String(255), nullable=True)
    variable_values = Column(JSON, nullable=True)  # e.g., {"1": "Contact.name", "2": "https://..."} or simple list/dict
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
