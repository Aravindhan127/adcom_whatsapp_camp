import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Integer
from sqlalchemy.sql import func
from app.core.database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True) # for URL/identifying orgs
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Limits
    max_users = Column(Integer, nullable=True) # None = Unlimited
    max_contacts = Column(Integer, nullable=True)
    max_campaigns = Column(Integer, nullable=True)

    # Relationships
    agents = relationship("Agent", back_populates="organization")
    config = relationship("OrganizationConfig", back_populates="organization", uselist=False)
    field_configs = relationship("ContactFieldConfig", back_populates="organization")

class OrganizationConfig(Base):
    __tablename__ = "organization_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), unique=True)
    
    # Meta WhatsApp Credentials
    whatsapp_business_id = Column(String(100), nullable=True)
    phone_number_id = Column(String(100), nullable=True)
    access_token = Column(Text, nullable=True)
    meta_app_id = Column(String(100), nullable=True)
    meta_app_secret = Column(String(100), nullable=True)
    waba_status = Column(String(50), default="pending")
    
    # Platform Configuration
    timezone = Column(String(50), default="Asia/Kolkata")
    webhook_verify_token = Column(String(255), nullable=True, default=lambda: str(uuid.uuid4()))
    
    organization = relationship("Organization", back_populates="config")

class ContactFieldConfig(Base):
    __tablename__ = "contact_field_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    
    field_name = Column(String(100), nullable=False) # e.g., "customer_id", "loyalty_points"
    field_label = Column(String(100), nullable=False) # e.g., "Customer ID"
    field_type = Column(String(20), default="text") # 'text', 'number', 'date', 'select'
    is_required = Column(Boolean, default=False)
    options = Column(JSON, nullable=True) # For 'select' type fields
    
    organization = relationship("Organization", back_populates="field_configs")
