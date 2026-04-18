from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from fastapi import Request
import logging

logger = logging.getLogger("adcom-api")

def log_action(
    db: Session,
    action: str,
    module: str,
    user_id: str = None,
    username: str = None,
    details: dict = None,
    request: Request = None
):
    """
    Centralized logging for critical actions.
    """
    try:
        ip = request.client.host if request else None
        
        audit_entry = AuditLog(
            action=action,
            module=module,
            user_id=user_id,
            username=username,
            details=details,
            ip_address=ip
        )
        db.add(audit_entry)
        db.commit()
        logger.info(f"AUDIT: [{module}] {action} by {username or 'SYSTEM'}")
    except Exception as e:
        logger.error(f"Failed to save audit log: {str(e)}")
        db.rollback()
