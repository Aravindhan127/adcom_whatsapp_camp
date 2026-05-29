from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from pydantic import BaseModel
from typing import Optional
import uuid
from app.core.security import (
    create_access_token, 
    verify_password, 
    get_password_hash, 
    RoleChecker, 
    PermissionChecker, 
    get_current_user,
    user_has_bypass
)
from app.models.agent import Agent
from app.models.rbac import Role
import logging

logger = logging.getLogger("adcom-api")

# Access control workers
admin_only = RoleChecker(["admin", "super_admin"])
super_admin_only = RoleChecker(["super_admin"])

router = APIRouter(prefix="/auth", tags=["auth"])

import re

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None
    role: str = "agent" # 'super_admin', 'admin', 'agent'
    organization_id: Optional[uuid.UUID] = None

    @staticmethod
    def validate_password(password: str) -> tuple[bool, str]:
        """Validate password complexity."""
        if len(password) < 8:
            return False, "Password must be at least 8 characters long"
        if not re.search(r'[A-Z]', password):
            return False, "Password must contain at least one uppercase letter"
        if not re.search(r'[a-z]', password):
            return False, "Password must contain at least one lowercase letter"
        if not re.search(r'\d', password):
            return False, "Password must contain at least one digit"
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False, "Password must contain at least one special character"
        return True, "Password is valid"

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/register")
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(PermissionChecker("org.manage"))
):
    # SECURITY: Validate password complexity
    is_valid, error_msg = UserCreate.validate_password(user_in.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Password validation failed: {error_msg}")

    # SECURITY: Validate email format
    if not UserCreate.validate_email(user_in.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # SECURITY: Validate username (alphanumeric and underscore only)
    if not re.match(r'^[a-zA-Z0-9_]+$', user_in.username):
        raise HTTPException(status_code=400, detail="Username can only contain letters, numbers, and underscores")

    # Check for existing user
    db_user = db.query(Agent).filter(
        (Agent.username == user_in.username) | (Agent.email == user_in.email)
    ).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or Email already registered")

    # SECURITY: Role & Org validation
    target_role = db.query(Role).filter(Role.slug == user_in.role).first()
    if not target_role:
        raise HTTPException(status_code=400, detail=f"Invalid role slug: {user_in.role}. Available: agent, admin, super_admin")

    # Use role_obj for checking current user permissions (refactoring away from hardcoded strings)
    can_bypass = user_has_bypass(current_user)
    
    if not can_bypass:
        # Admin can create users in their own organization, but cannot assign global bypass roles
        if target_role.can_bypass_isolation:
             raise HTTPException(status_code=403, detail="As an Organization Admin, you cannot assign roles with global isolation bypass privileges.")
        
        user_in.organization_id = current_user.organization_id
    else:
        # Super Admin can create any role. 
        # If creating Admin or Agent (roles without isolation bypass), ensure organization_id is provided.
        if not target_role.can_bypass_isolation and not user_in.organization_id:
             raise HTTPException(status_code=400, detail=f"The role '{target_role.name}' must be assigned to an Organization. Please select one from the dropdown.")
    
    new_user = Agent(
        id=uuid.uuid4(),
        username=user_in.username,
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role, # Keep legacy string for now
        role_id=target_role.id,
        organization_id=user_in.organization_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info(f"New User Registered: {new_user.username} (Role: {new_user.role}, Org: {new_user.organization_id})")
    return {"msg": f"User {new_user.username} created with role {new_user.role}"}

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Agent).filter(Agent.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Login failed for user: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.info(f"User Logged In: {user.username}")
    
    access_token = create_access_token(data={
        "sub": str(user.id), 
        "role": user.role_obj.slug if user.role_obj else user.role,
        "org_id": str(user.organization_id) if user.organization_id else None,
        "token_version": user.token_version
    })
    
    permission_slugs = [p.slug for p in user.role_obj.permissions] if user.role_obj else []

    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "role": user.role_obj.slug if user.role_obj else user.role,
        "username": user.username,
        "permissions": permission_slugs
    }

@router.get("/me")
def get_me(current_user: Agent = Depends(get_current_user)):
    """Fetch the currently logged in user's profile and permissions."""
    permission_slugs = [p.slug for p in current_user.role_obj.permissions] if current_user.role_obj else []
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role_obj.slug if current_user.role_obj else current_user.role,
        "organization_id": str(current_user.organization_id) if current_user.organization_id else None,
        "permissions": permission_slugs
    }

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(Agent).filter(Agent.email == request.email).first()
    # Always return success to prevent email enumeration
    if user:
        from app.core.security import create_reset_token
        from app.core.database import logger
        token = create_reset_token(user.email)
        
        # MOCK EMAIL SENDING
        frontend_url = "http://localhost:5173" # Default Vite port
        reset_link = f"{frontend_url}/reset-password?token={token}"
        
        logger.info("\n" + "="*50)
        logger.info(f"PASSWORD RESET REQUEST FOR: {user.email}")
        logger.info(f"RESET LINK: {reset_link}")
        logger.info(f"TOKEN: {token}")
        logger.info("="*50 + "\n")
        
    return {"msg": "If an account exists for this email, a reset link has been generated."}

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    from app.core.security import verify_reset_token
    email = verify_reset_token(request.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # SECURITY: Validate new password complexity
    is_valid, error_msg = UserCreate.validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Password validation failed: {error_msg}")

    user = db.query(Agent).filter(Agent.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(request.new_password)
    db.commit()
    return {"msg": "Password updated successfully"}
