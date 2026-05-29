from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from uuid import UUID
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user, PermissionChecker, verify_org_access, user_has_bypass
from app.models.agent import Agent
from app.models.organization import Organization, OrganizationConfig, ContactFieldConfig
from app.models.rbac import Role, Permission
from app.core.security import create_access_token
from app.services.audit_service import log_action
import re

router = APIRouter(prefix="/admin", tags=["Super Admin Management"])

# Permissions
require_system_admin = PermissionChecker("system.admin")
require_org_manage = PermissionChecker(["system.admin", "org.manage"])
require_user_manage = PermissionChecker(["system.admin", "user.manage"])
require_role_manage = PermissionChecker(["system.admin", "role.manage"])



# ──────────────────────────────────────────────────────────────
# Pydantic Schemas
# ──────────────────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str
    slug: str

class OrgConfigUpdate(BaseModel):
    whatsapp_business_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    access_token: Optional[str] = None
    meta_app_id: Optional[str] = None
    meta_app_secret: Optional[str] = None
    timezone: Optional[str] = "Asia/Kolkata"
    
    # Optional fields that might be sent by the frontend
    id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    waba_status: Optional[str] = None
    webhook_verify_token: Optional[str] = None
    
    class Config:
        extra = "ignore" # Allow extra fields without validation error

class UserUpdate(BaseModel):
    role_id: Optional[uuid.UUID] = None
    organization_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

class FieldConfigCreate(BaseModel):
    field_name: str
    field_label: str
    field_type: str = "text"
    is_required: bool = False
    options: Optional[List[str]] = None

class RoleCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    
class RolePermissionsUpdate(BaseModel):
    permission_ids: List[uuid.UUID]

# ──────────────────────────────────────────────────────────────
# DYNAMIC FIELDS MANAGEMENT (SUPER ADMIN ONLY)
# ──────────────────────────────────────────────────────────────

@router.get("/system/organizations/{org_id}/fields")
def list_org_custom_fields(
    org_id: UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """List all custom fields configured for an organization."""
    fields = db.query(ContactFieldConfig).filter(ContactFieldConfig.organization_id == org_id).all()
    return fields

@router.post("/system/organizations/{org_id}/fields")
def configure_custom_field(
    org_id: UUID,
    field_data: dict, # Using dict for flexibility (field_name, field_label, field_type, is_required, options)
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """Create or update a custom field configuration for an organization."""
    field_name = field_data.get("field_name")
    if not field_name:
        raise HTTPException(status_code=400, detail="field_name is required")
        
    # Check if field already exists for this org
    existing = db.query(ContactFieldConfig).filter(
        ContactFieldConfig.organization_id == org_id,
        ContactFieldConfig.field_name == field_name
    ).first()
    
    if existing:
        print(f"RBAC: Updating existing field '{field_name}' for org {org_id}")
        existing.field_label = field_data.get("field_label", existing.field_label)
        existing.field_type = field_data.get("field_type", existing.field_type)
        existing.is_required = field_data.get("is_required", existing.is_required)
        existing.options = field_data.get("options", existing.options)
        db.commit()
        return existing
    
    print(f"RBAC: Creating new custom field '{field_name}' for org {org_id}")
    new_field = ContactFieldConfig(
        organization_id=org_id,
        field_name=field_name,
        field_label=field_data.get("field_label", field_name),
        field_type=field_data.get("field_type", "text"),
        is_required=field_data.get("is_required", False),
        options=field_data.get("options", [])
    )
    db.add(new_field)
    db.commit()
    db.refresh(new_field)
    return new_field

@router.delete("/system/organizations/{org_id}/fields/{field_id}")
def delete_custom_field(
    org_id: UUID,
    field_id: UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """Delete a custom field configuration."""
    field = db.query(ContactFieldConfig).filter(
        ContactFieldConfig.id == field_id,
        ContactFieldConfig.organization_id == org_id
    ).first()
    
    if not field:
        raise HTTPException(status_code=404, detail="Field config not found")
        
    db.delete(field)
    db.commit()
    return {"status": "success", "message": f"Field {field.field_name} removed from config"}

# ──────────────────────────────────────────────────────────────
# Organization Routes
# ──────────────────────────────────────────────────────────────

@router.get("/organizations")
def list_organizations(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """List all organizations globally (Super Admin only)."""
    orgs = db.query(Organization).all()
    results = []
    for org in orgs:
        # Count members and campaigns for stats
        member_count = db.query(Agent).filter(Agent.organization_id == org.id).count()
        results.append({
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "member_count": member_count,
            "is_active": org.is_active,
            "created_at": org.created_at
        })
    return results

@router.post("/organizations")
def create_organization(
    org_in: OrgCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """Create a new organization/tenant."""
    # Check if slug exists
    if db.query(Organization).filter(Organization.slug == org_in.slug).first():
        raise HTTPException(status_code=400, detail="Slug already in use")
    
    new_org = Organization(name=org_in.name, slug=org_in.slug)
    db.add(new_org)
    db.flush() # Get ID
    
    # Create empty config
    config = OrganizationConfig(organization_id=new_org.id)
    db.add(config)
    
    db.commit()
    db.refresh(new_org)
    
    log_action(
        db, "CREATE_ORG", "SYSTEM", 
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username, 
        organization_id=current_user.organization_id,
        details={"org_name": org_in.name}
    )
    
    return new_org

@router.get("/organizations/{org_id}/config")
def get_org_config(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """Get Meta configuration for an organization (Super Admin)."""
    print(f"RBAC: Fetching config for org {org_id} by Super Admin {current_user.username}")
    
    config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == org_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config

@router.patch("/organizations/{org_id}/config")
def update_org_config(
    org_id: uuid.UUID,
    config_in: OrgConfigUpdate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """Update Meta credentials for an organization (Super Admin)."""
    print(f"RBAC: Updating config for org {org_id} by Super Admin {current_user.username}")
    print(f"DEBUG: Received config: {config_in.dict()}")
        
    config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == org_id).first()
    if not config:
        config = OrganizationConfig(organization_id=org_id)
        db.add(config)
    
    if config_in.whatsapp_business_id is not None: config.whatsapp_business_id = config_in.whatsapp_business_id
    if config_in.phone_number_id is not None: config.phone_number_id = config_in.phone_number_id
    if config_in.access_token is not None: config.access_token = config_in.access_token
    if config_in.meta_app_id is not None: config.meta_app_id = config_in.meta_app_id
    if config_in.meta_app_secret is not None: config.meta_app_secret = config_in.meta_app_secret
    if config_in.timezone is not None: config.timezone = config_in.timezone
    if config_in.webhook_verify_token is not None: config.webhook_verify_token = config_in.webhook_verify_token
    
    db.commit()
    
    log_action(
        db, "UPDATE_ORG_CONFIG", "SYSTEM", 
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username, 
        organization_id=org_id,
        details={"whatsapp_business_id": config_in.whatsapp_business_id}
    )
    
    return {"message": "Configuration updated"}

@router.get("/organizations/{org_id}/fields")
def list_org_custom_fields(
    org_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """List custom contact fields for a specific tenant (Super Admin)."""
    return db.query(ContactFieldConfig).filter(ContactFieldConfig.organization_id == org_id).all()

@router.post("/organizations/{org_id}/fields")
def add_org_custom_field(
    org_id: uuid.UUID,
    field_in: FieldConfigCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """Add a new custom field to a tenant's schema (Super Admin)."""
    # Sanitize field name
    safe_name = re.sub(r'[^a-z0-9_]', '', field_in.field_name.lower())
    
    existing = db.query(ContactFieldConfig).filter(
        ContactFieldConfig.organization_id == org_id,
        ContactFieldConfig.field_name == safe_name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Field name already exists for this tenant")
        
    new_field = ContactFieldConfig(
        organization_id=org_id,
        field_name=safe_name,
        field_label=field_in.field_label,
        field_type=field_in.field_type,
        is_required=field_in.is_required,
        options=field_in.options
    )
    db.add(new_field)
    db.commit()
    return new_field

@router.delete("/organizations/{org_id}/fields/{field_id}")
def delete_org_custom_field(
    org_id: uuid.UUID,
    field_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_system_admin)
):
    """Remove a custom field from a tenant's schema (Super Admin)."""
    field = db.query(ContactFieldConfig).filter(
        ContactFieldConfig.id == field_id,
        ContactFieldConfig.organization_id == org_id
    ).first()
    
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
        
    db.delete(field)
    db.commit()
    return {"message": "Field deleted"}

# ──────────────────────────────────────────────────────────────
# User Management Routes
# ──────────────────────────────────────────────────────────────

@router.get("/users")
def list_all_users(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_user_manage)
):
    """List users. Org Admins only see their own org's users."""
    if user_has_bypass(current_user):
        users = db.query(Agent).all()
    else:
        users = db.query(Agent).filter(Agent.organization_id == current_user.organization_id).all()
    results = []
    for u in users:
        results.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role, # String for compat
            "role_name": u.role_obj.name if u.role_obj else "No Role",
            "role_id": u.role_id,
            "organization_name": u.organization.name if u.organization else "No Org",
            "organization_id": u.organization_id,
            "is_active": u.is_active,
            "created_at": u.created_at
        })
    return results

@router.patch("/users/{user_id}")
def update_user_access(
    user_id: uuid.UUID,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_user_manage)
):
    """Change a user's role or organization (Super Admin only)."""
    target_user = db.query(Agent).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user_has_bypass(current_user) and target_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot manage users outside your organization")
        
    if not user_has_bypass(current_user) and target_user.role_obj and target_user.role_obj.can_bypass_isolation:
        raise HTTPException(status_code=403, detail="Cannot modify users with global isolation bypass privileges")
        
    if user_in.role_id is not None:
        role = db.query(Role).get(user_in.role_id)
        if not role:
             raise HTTPException(status_code=400, detail="Invalid Role ID")
             
        if not user_has_bypass(current_user) and role.can_bypass_isolation:
             raise HTTPException(status_code=403, detail="Cannot assign roles with global isolation bypass privileges")
             
        target_user.role_id = role.id
        target_user.role = role.slug # Keep synced
        
    if user_in.organization_id is not None:
        if not user_has_bypass(current_user) and user_in.organization_id != current_user.organization_id:
            raise HTTPException(status_code=403, detail="Cannot move users to other organizations")
        org = db.query(Organization).get(user_in.organization_id)
        if not org:
             raise HTTPException(status_code=400, detail="Invalid Organization ID")
        target_user.organization_id = org.id
        
    if user_in.is_active is not None:
        target_user.is_active = user_in.is_active
        
    # SECURITY: Invalidate current sessions so new permissions/org apply immediately
    target_user.token_version += 1
    
    db.commit()
    return {"message": f"User {target_user.username} updated successfully. All active sessions invalidated."}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_user_manage)
):
    """Permanently delete a user account (Super Admin only)."""
    target_user = db.query(Agent).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user_has_bypass(current_user) and target_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot delete users outside your organization")
        
    if not user_has_bypass(current_user) and target_user.role_obj and target_user.role_obj.can_bypass_isolation:
        raise HTTPException(status_code=403, detail="Cannot delete users with global isolation bypass privileges")
        
    db.delete(target_user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.get("/roles")
def list_available_roles(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_role_manage)
):
    """Get list of roles for assignment. Org Admins cannot see bypass roles."""
    from sqlalchemy.orm import joinedload
    query = db.query(Role).options(joinedload(Role.permissions))
    
    if not user_has_bypass(current_user):
        query = query.filter(Role.can_bypass_isolation == False)
        
    roles = query.all()
    results = []
    for r in roles:
        results.append({
            "id": r.id,
            "name": r.name,
            "slug": r.slug,
            "description": r.description,
            "can_bypass_isolation": r.can_bypass_isolation,
            "permission_ids": [p.id for p in r.permissions]
        })
    return results

@router.post("/roles")
def create_role(
    role_in: RoleCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_role_manage)
):
    """Create a new custom role."""
    if db.query(Role).filter(Role.slug == role_in.slug).first():
        raise HTTPException(status_code=400, detail="Role slug already exists")
    
    new_role = Role(
        name=role_in.name,
        slug=role_in.slug,
        description=role_in.description
    )
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    return new_role

@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_role_manage)
):
    """List all available permissions, grouped by module."""
    perms = db.query(Permission).all()
    grouped = {}
    for p in perms:
        if p.module not in grouped:
            grouped[p.module] = []
        grouped[p.module].append({
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "type": p.type,
            "description": p.description
        })
    return grouped

@router.put("/roles/{role_id}/permissions")
def update_role_permissions(
    role_id: uuid.UUID,
    perms_in: RolePermissionsUpdate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_role_manage)
):
    """Update permissions assigned to a role."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    permissions = db.query(Permission).filter(Permission.id.in_(perms_in.permission_ids)).all()
    if len(permissions) != len(perms_in.permission_ids):
        raise HTTPException(status_code=400, detail="One or more invalid permission IDs")
        
    # Update the permissions relationship
    role.permissions = permissions
        
    # SECURITY: Invalidate tokens for all users of this role so permissions apply immediately,
    # EXCEPT for the current user who made the change, so they aren't unceremoniously logged out.
    # The frontend is responsible for fetching fresh permissions via /auth/me for the current user.
    users_with_role = db.query(Agent).filter(Agent.role_id == role.id).all()
    for u in users_with_role:
        if u.id != current_user.id:
            u.token_version += 1
    
    db.commit()
    return {"message": f"Role permissions updated. Sessions for all other {role.name}s invalidated."}

@router.post("/users/{user_id}/impersonate")
def impersonate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_user_manage)
):
    """Generate an access token to impersonate another user (Super Admin only)."""
    target_user = db.query(Agent).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user_has_bypass(current_user) and target_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot impersonate users outside your organization")
        
    # Prevent impersonating users who can bypass isolation (other Super Admins)
    if target_user.role_obj and target_user.role_obj.can_bypass_isolation:
        raise HTTPException(status_code=403, detail="Cannot impersonate users with global isolation bypass privileges")
        
    log_action(db, "IMPERSONATE_USER", "SYSTEM", user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username, details={"target_user": target_user.username})
    
    access_token = create_access_token(data={
        "sub": str(target_user.id), 
        "role": target_user.role_obj.slug if target_user.role_obj else target_user.role,
        "org_id": str(target_user.organization_id) if target_user.organization_id else None,
        "token_version": target_user.token_version,
        "impersonator_id": str(current_user.id) # Traceability
    })
    
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": target_user.role_obj.slug if target_user.role_obj else target_user.role,
        "username": target_user.username
    }

@router.post("/users/{user_id}/force-logout")
def force_logout(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_user_manage)
):
    """Invalidate all active sessions for a user by incrementing token_version."""
    target_user = db.query(Agent).get(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user_has_bypass(current_user) and target_user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=403, detail="Cannot force logout users outside your organization")
        
    target_user.token_version += 1
    db.commit()
    
    log_action(db, "FORCE_LOGOUT", "SYSTEM", user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username, details={"target_user": target_user.username})
    
    return {"message": f"All active sessions for {target_user.username} have been invalidated."}
