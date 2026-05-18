from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import uuid
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.core.security import get_current_user, user_has_bypass, PermissionChecker
from app.models.agent import Agent

router = APIRouter(prefix="/audit", tags=["Audit"])
admin_only = PermissionChecker("org.manage")

@router.get("/logs", summary="Get System Audit Logs")
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    organization_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    """
    Fetch system-wide audit logs. Restricted to admins.
    """
    # Join with Organization to get the name
    from app.models.organization import Organization
    query = db.query(AuditLog, Organization.name.label("organization_name")).outerjoin(
        Organization, AuditLog.organization_id == Organization.id
    )
    
    # Isolation: Filter by organization if not super admin
    if not user_has_bypass(current_user):
        query = query.filter(AuditLog.organization_id == current_user.organization_id)
    elif organization_id:
        # Super admin can explicitly filter by organization
        query = query.filter(AuditLog.organization_id == organization_id)
    
    if module:
        query = query.filter(AuditLog.module == module)
    if action:
        query = query.filter(AuditLog.action == action)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (AuditLog.username.ilike(search_filter)) |
            (AuditLog.action.ilike(search_filter)) |
            (AuditLog.module.ilike(search_filter))
        )
        
    total = query.count()
    results_raw = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    items = []
    for log, org_name in results_raw:
        # Convert model to dict and add org_name
        log_dict = {
            "id": log.id,
            "action": log.action,
            "module": log.module,
            "user_id": log.user_id,
            "username": log.username,
            "organization_id": str(log.organization_id) if log.organization_id else None,
            "organization_name": org_name or "System",
            "details": log.details,
            "timestamp": log.timestamp.isoformat(),
            "ip_address": log.ip_address
        }
        items.append(log_dict)
    
    return {
        "total": total,
        "items": items,
        "skip": skip,
        "limit": limit
    }
