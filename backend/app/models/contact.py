import enum
import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class ContactStatus(str, enum.Enum):
    VALID = "valid"
    INVALID = "invalid"
    BLOCKED = "blocked"

class ContactSource(str, enum.Enum):
    CSV = "csv"
    EXCEL = "excel"
    MANUAL = "manual"
    API = "api"

class ImportStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ContactList(Base):
    __tablename__ = "contact_lists"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    contacts = relationship("Contact", back_populates="contact_list")

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(20), nullable=False, index=True)
    name = Column(String(255), nullable=True)
    country_code = Column(String(5), nullable=True)
    status = Column(String(20), default=ContactStatus.VALID.value, index=True)
    source = Column(String(20), default=ContactSource.MANUAL.value)
    
    # New Optional Segmentation Fields
    company_name = Column(String(255), nullable=True)
    lead_source = Column(String(100), nullable=True)
    date_of_birth = Column(DateTime, nullable=True) # Using DateTime for compatibility, or Date
    customer_category = Column(String(100), nullable=True) # SI / Distributor / Super Stockist
    customer_stage = Column(String(100), nullable=True) # Prospective / New / Old / Cancelled
    city = Column(String(100), nullable=True)
    product_service_interest = Column(Text, nullable=True)
    consent_confirmation = Column(String(255), nullable=True) # Opt-in proof
    
    list_id = Column(UUID(as_uuid=True), ForeignKey("contact_lists.id"), nullable=True, index=True)
    contact_list = relationship("ContactList", back_populates="contacts")
    import_id = Column(UUID(as_uuid=True), ForeignKey("import_history.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ImportHistory(Base):
    __tablename__ = "import_history"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    records_count = Column(Integer, default=0)
    uploaded_by = Column(String(255), nullable=True)
    status = Column(String(20), default=ImportStatus.PENDING.value)
    success_count = Column(Integer, default=0)
    duplicate_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    contacts = relationship("Contact", backref="import_record")
