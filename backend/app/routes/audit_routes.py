from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.core.security import RoleChecker, get_current_user
from app.models.agent import Agent

router = APIRouter(prefix="/audit", tags=["Audit"])
admin_only = RoleChecker(["admin"])

@router.get("/logs", summary="Get System Audit Logs")
def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    module: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    """
    Fetch system-wide audit logs. Restricted to admins.
    """
    query = db.query(AuditLog)
    
    if module:
        query = query.filter(AuditLog.module == module)
    if action:
        query = query.filter(AuditLog.action == action)
        
    total = query.count()
    items = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "items": items,
        "skip": skip,
        "limit": limit
    }
