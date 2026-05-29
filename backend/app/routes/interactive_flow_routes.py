import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.models.interactive_flow import InteractiveFlow
from app.models.agent import Agent
from app.core.security import get_current_user, PermissionChecker, verify_org_access, user_has_bypass
from app.services.audit_service import log_action

logger = logging.getLogger("adcom-api")

router = APIRouter(prefix="/flows", tags=["Interactive Flows"])

require_view = PermissionChecker(["template.view", "campaign.view"])
require_manage = PermissionChecker(["template.manage", "campaign.manage"])

class FlowBase(BaseModel):
    name: str
    trigger_keyword: str
    response_type: str  # 'text' or 'template'
    response_text: Optional[str] = None
    response_template: Optional[str] = None
    variable_values: Optional[dict] = None
    is_active: bool = True

class FlowCreate(FlowBase):
    pass

class FlowUpdate(BaseModel):
    name: Optional[str] = None
    trigger_keyword: Optional[str] = None
    response_type: Optional[str] = None
    response_text: Optional[str] = None
    response_template: Optional[str] = None
    variable_values: Optional[dict] = None
    is_active: Optional[bool] = None

@router.get("/")
def list_flows(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    current_user: Agent = Depends(require_view)
):
    query = db.query(InteractiveFlow)
    
    # Isolation Scoping
    if not user_has_bypass(current_user):
        query = query.filter(InteractiveFlow.organization_id == current_user.organization_id)
        
    if search:
        query = query.filter(
            (InteractiveFlow.name.ilike(f"%{search}%")) |
            (InteractiveFlow.trigger_keyword.ilike(f"%{search}%"))
        )
        
    total = query.count()
    items = query.order_by(InteractiveFlow.created_at.desc()).offset(skip).limit(limit).all()
    
    return {"total": total, "items": items}

@router.post("/")
def create_flow(
    flow_in: FlowCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    # Enforce trigger keyword uniqueness per organization
    existing_query = db.query(InteractiveFlow).filter(
        InteractiveFlow.trigger_keyword.ilike(flow_in.trigger_keyword.strip())
    )
    if not user_has_bypass(current_user):
        existing_query = existing_query.filter(InteractiveFlow.organization_id == current_user.organization_id)
    existing = existing_query.first()
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"An interactive flow with trigger keyword '{flow_in.trigger_keyword}' already exists in your organization."
        )

    new_flow = InteractiveFlow(
        name=flow_in.name,
        trigger_keyword=flow_in.trigger_keyword.strip(),
        response_type=flow_in.response_type,
        response_text=flow_in.response_text,
        response_template=flow_in.response_template,
        variable_values=flow_in.variable_values,
        is_active=flow_in.is_active,
        organization_id=current_user.organization_id
    )
    db.add(new_flow)
    db.commit()
    db.refresh(new_flow)

    log_action(
        db, "CREATE_INTERACTIVE_FLOW", "INTERACTIVE_FLOWS",
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
        organization_id=current_user.organization_id,
        details={"flow_id": str(new_flow.id), "name": new_flow.name, "trigger_keyword": new_flow.trigger_keyword},
        request=request
    )

    return new_flow

@router.put("/{flow_id}")
def update_flow(
    flow_id: uuid.UUID,
    flow_in: FlowUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    flow = db.query(InteractiveFlow).filter(InteractiveFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Interactive flow not found")
        
    verify_org_access(current_user, flow.organization_id)

    # Check for keyword conflicts if trigger_keyword is being updated
    if flow_in.trigger_keyword and flow_in.trigger_keyword.strip().lower() != flow.trigger_keyword.lower():
        existing_query = db.query(InteractiveFlow).filter(
            InteractiveFlow.trigger_keyword.ilike(flow_in.trigger_keyword.strip()),
            InteractiveFlow.id != flow_id
        )
        if not user_has_bypass(current_user):
            existing_query = existing_query.filter(InteractiveFlow.organization_id == current_user.organization_id)
        existing = existing_query.first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"An interactive flow with trigger keyword '{flow_in.trigger_keyword}' already exists in your organization."
            )

    # Update fields
    update_data = flow_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if field == "trigger_keyword" and val:
            setattr(flow, field, val.strip())
        else:
            setattr(flow, field, val)

    db.commit()
    db.refresh(flow)

    log_action(
        db, "UPDATE_INTERACTIVE_FLOW", "INTERACTIVE_FLOWS",
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
        organization_id=current_user.organization_id,
        details={"flow_id": str(flow.id), "name": flow.name},
        request=request
    )

    return flow

@router.delete("/{flow_id}")
def delete_flow(
    flow_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    flow = db.query(InteractiveFlow).filter(InteractiveFlow.id == flow_id).first()
    if not flow:
        raise HTTPException(status_code=404, detail="Interactive flow not found")

    verify_org_access(current_user, flow.organization_id)

    flow_name = flow.name
    db.delete(flow)
    db.commit()

    log_action(
        db, "DELETE_INTERACTIVE_FLOW", "INTERACTIVE_FLOWS",
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
        organization_id=current_user.organization_id,
        details={"flow_id": str(flow_id), "name": flow_name},
        request=request
    )

    return {"message": f"Interactive flow '{flow_name}' deleted successfully."}
