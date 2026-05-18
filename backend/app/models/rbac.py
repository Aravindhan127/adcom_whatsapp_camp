import uuid
from sqlalchemy import Column, String, Boolean, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

# Association table for Many-to-Many relationship between Roles and Permissions
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True),
)

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False) # e.g., 'Super Admin', 'Admin', 'Agent'
    slug = Column(String(50), unique=True, nullable=False) # e.g., 'superadmin', 'admin', 'agent'
    description = Column(String(255), nullable=True)
    can_bypass_isolation = Column(Boolean, default=False) # Key for "The Suprem" Super Admin
    
    # Relationships
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    agents = relationship("Agent", back_populates="role_obj")

class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False) # e.g., 'campaign.start', 'contact.delete'
    description = Column(String(255), nullable=True)
    module = Column(String(50), nullable=False, default="General") # e.g., 'Campaigns', 'Contacts', 'Settings'
    type = Column(String(50), nullable=False, default="action") # 'screen' or 'action'
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
