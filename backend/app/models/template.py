import uuid
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base

class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, index=True, nullable=False)
    category = Column(String(50), nullable=False) # 'MARKETING', 'UTILITY', 'AUTHENTICATION'
    language = Column(String(10), default="en")
    status = Column(String(20), default="PENDING") # 'APPROVED', 'REJECTED', 'PENDING', 'PAUSED'
    meta_template_id = Column(String(100), unique=True, index=True, nullable=True) # ID from Meta
    rejection_reason = Column(Text, nullable=True) # Reason why Meta rejected it
    
    # Content
    components = Column(JSON, nullable=False) # List of header, body, footer, buttons
    
    # Store variable mappings for dispatch resolution
    variable_mappings = Column(JSON, nullable=True) # e.g. {"1": "name", "2": "company"}
    media_id = Column(String(255), nullable=True) # Permanent Meta Media ID for sending campaigns

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
