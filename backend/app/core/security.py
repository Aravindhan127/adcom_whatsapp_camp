from datetime import datetime, timedelta, timezone
import uuid
from typing import Optional
from fastapi import Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.agent import Agent
from app.core.config import settings
import jwt
import bcrypt

# Native bcrypt only - passlib removed due to Python 3.13 incompatibility
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

def truncate_password_bytes(password: str) -> bytes:
    """Bcrypt has a 72-byte limit. Truncate UTF-8 bytes to 72 and return bytes."""
    if not password:
        return b""
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        # We truncate bytes, but we must ensure we don't leave a partial multi-byte char
        # which could cause issues if it's ever decoded. 
        # However, bcrypt only cares about the bytes.
        password_bytes = password_bytes[:72]
    return password_bytes

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if not hashed_password:
            return False
        # Native bcrypt expects bytes
        password_bytes = truncate_password_bytes(plain_password)
        hash_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        import logging
        logging.getLogger("adcom-api").error(f"verify_password error: {e}")
        return False

def get_password_hash(password: str) -> str:
    # Native bcrypt returns bytes, we store as string
    password_bytes = truncate_password_bytes(password)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

from app.models.rbac import Role, Permission
from sqlalchemy.orm import joinedload

def get_current_user(
    db: Session = Depends(get_db), 
    token: str = Depends(oauth2_scheme)
) -> Agent:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    import uuid
    try:
        valid_uuid = uuid.UUID(user_id_str)
    except ValueError:
        # Legacy token with username instead of UUID
        raise credentials_exception

    # Pre-fetch role and permissions to avoid N+1 queries during permission checks
    print(f"DEBUG: get_current_user running with valid_uuid={valid_uuid!r} (type: {type(valid_uuid)}) user_id_str={user_id_str!r}")
    user = db.query(Agent).options(
        joinedload(Agent.role_obj).joinedload(Role.permissions)
    ).filter(Agent.id == valid_uuid).first()

    if user is None:
        raise credentials_exception
        
    token_version = payload.get("token_version")
    if token_version is not None and token_version != user.token_version:
        raise credentials_exception
        
    # Security Fix: Set impersonator_id on the user object if present
    impersonator_id = payload.get("impersonator_id")
    if impersonator_id:
        user.impersonator_id = impersonator_id
        
    return user

def verify_org_access(user: Agent, resource_org_id: Optional[uuid.UUID]):
    """
    Centralized utility to enforce multi-tenant isolation.
    If the user's role has 'can_bypass_isolation' (e.g. Super Admin), access is granted globally.
    Otherwise, the resource MUST belong to the user's organization.
    """
    # 1. Check Role Object (New RBAC system)
    if user.role_obj:
        if user.role_obj.can_bypass_isolation:
            return True
        if user.organization_id == resource_org_id:
            return True
    
    # 2. Check Role String (Legacy fallback)
    if user.role in ["super_admin", "superadmin"]:
        return True
        
    # 3. Final Isolation Check
    if user.organization_id != resource_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This resource does not belong to your organization"
        )
    return True

def user_has_bypass(user: Agent) -> bool:
    """
    Check if a user is a Super Admin who can bypass multi-tenant isolation.
    """
    if user.role_obj and user.role_obj.can_bypass_isolation:
        return True
    return user.role in ["super_admin", "superadmin"]

class PermissionChecker:
    """
    Dynamic replacement for RoleChecker.
    Checks if the user's assigned role contains the required permission slug(s).
    Supports a single string or a list of strings (OR-logic).
    """
    def __init__(self, required_permissions: str | list[str]):
        if isinstance(required_permissions, str):
            self.required_permissions = [required_permissions]
        else:
            self.required_permissions = required_permissions

    def __call__(self, user: Agent = Depends(get_current_user)):
        # Notice: Super Admins no longer bypass permission checks.
        # They MUST have the permission assigned in the database matrix.
        # Isolation bypass is handled separately in verify_org_access.

        if not user.role_obj:
            print(f"DEBUG: Permission DENIED - No role object for user: {user.username} (Role string: {user.role})")
            raise HTTPException(status_code=403, detail="Role not assigned or session expired. Please re-login.")

        user_permissions = {p.slug for p in user.role_obj.permissions}
        
        # Check if any of the required permissions are present (OR-logic)
        has_permission = any(perm in user_permissions for perm in self.required_permissions)
        
        if not has_permission:
            print(f"DEBUG: Permission DENIED for user: {user.username}. Missing: {self.required_permissions}. Has: {list(user_permissions)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission(s): {', '.join(self.required_permissions)}"
            )
        return user

class RoleChecker:
    """
    Maintained for backward compatibility during transition.
    Checks against role slugs.
    """
    def __init__(self, allowed_role_slugs: list[str]):
        self.allowed_role_slugs = allowed_role_slugs

    def __call__(self, user: Agent = Depends(get_current_user)):
        # Rule: superadmin has access to everything
        if user.role_obj and user.role_obj.can_bypass_isolation:
            return user
            
        role_slug = user.role_obj.slug if user.role_obj else user.role
        if role_slug not in self.allowed_role_slugs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action"
            )
        return user

def get_current_user_flexible(
    db: Session = Depends(get_db), 
    token_header: Optional[str] = Depends(OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)),
    token_query: Optional[str] = Query(None, alias="token")
) -> Agent:
    """
    Flexible auth that follows Rule 12: Support URL-token for <img> tags while
    maintaining standard Bearer auth for API calls.
    """
    token = token_header or token_query
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not token:
        raise credentials_exception

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    import uuid
    try:
        valid_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception
        
    print(f"DEBUG: flexible running with valid_uuid={valid_uuid!r}")
    user = db.query(Agent).options(
        joinedload(Agent.role_obj).joinedload(Role.permissions)
    ).filter(Agent.id == valid_uuid).first()
    if user is None:
        raise credentials_exception
        
    token_version = payload.get("token_version")
    if token_version is not None and token_version != user.token_version:
        raise credentials_exception
        
    return user

def create_reset_token(email: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode = {"exp": expire, "sub": email, "purpose": "password_reset"}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def verify_reset_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("purpose") != "password_reset":
            return None
        return payload.get("sub")
    except jwt.PyJWTError:
        return None
