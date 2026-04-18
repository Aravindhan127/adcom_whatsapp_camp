import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey
from app.core.database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action = Column(String(100), nullable=False, index=True) # e.g. "CREATE_CAMPAIGN", "DELETE_TEMPLATE"
    module = Column(String(50), nullable=False, index=True) # e.g. "CAMPAIGNS", "CONTACTS", "SYSTEM"
    user_id = Column(String(36), nullable=True, index=True)
    username = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True) # Context data like campaign_id, old_value, new_value
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = Column(String(50), nullable=True)
