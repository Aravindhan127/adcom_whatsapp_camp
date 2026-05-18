from fastapi import APIRouter, Depends, HTTPException, Body, Query, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.template import WhatsAppTemplate
from pydantic import BaseModel
from typing import List, Optional
from app.services.meta_api import (
    create_meta_template, 
    update_meta_template,
    get_meta_templates_status, 
    create_resumable_upload_session, 
    upload_file_content, 
    delete_meta_template
)
from datetime import datetime, timezone
import uuid
import logging
from app.core.security import get_current_user, RoleChecker, verify_org_access, PermissionChecker, user_has_bypass, user_has_bypass
from app.models.agent import Agent
from app.models.campaign import Campaign
from app.models.organization import OrganizationConfig
from app.services.audit_service import log_action
from fastapi import Request

import re

logger = logging.getLogger("adcom-api")

# Access control workers
require_view = PermissionChecker("template.view")
require_manage = PermissionChecker("template.manage")
require_sync = PermissionChecker("template.sync")
admin_only = PermissionChecker("org.manage")
any_agent = get_current_user

router = APIRouter(prefix="/templates", tags=["Templates"])

def validate_template_body(components: list):
    """
    Validates that no BODY component text ends with a variable placeholder like {{1}}.
    Meta rejects templates where the body ends with a variable — text must follow.
    """
    for comp in components:
        if comp.get("type", "").upper() == "BODY":
            body_text = comp.get("text", "").strip()
            if re.search(r"\{\{\d+\}\}$", body_text):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Invalid template body: Message cannot end with a variable like {{1}}. "
                        "Please add text after the last variable. "
                        'Example: \'Hi {{1}}, welcome!\' \u2705 | Invalid: \'Hi {{1}}\' \u274c'
                    )
                )

def check_template_in_use(db: Session, template_name: str) -> bool:
    """
    Check if a template is currently assigned to any ACTIVE campaign.
    Active means: running, scheduled, or on_hold.
    """
    active_statuses = ["running", "scheduled", "on_hold"]
    in_use = db.query(Campaign).filter(
        Campaign.template_name == template_name,
        Campaign.status.in_(active_statuses)
    ).first()
    return in_use is not None

class TemplateCreate(BaseModel):
    name: str
    category: str
    language: str = "en_US"
    components: List[dict]
    variable_mappings: Optional[dict] = None
    media_id: Optional[str] = None
    submit_to_meta: bool = False

@router.post("/")
def create_template(
    template_in: TemplateCreate, 
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    existing_query = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == template_in.name)
    if not user_has_bypass(current_user):
        existing_query = existing_query.filter(WhatsAppTemplate.organization_id == current_user.organization_id)
    existing = existing_query.first()
    if existing:
        raise HTTPException(status_code=400, detail="Template name already exists in your organization")
    
    # Validate: body must not end with a variable
    validate_template_body(template_in.components)
    
    meta_id = None
    status = "LOCAL_ONLY"
    
    if template_in.submit_to_meta:
        # Fetch Org Config for credentials
        config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == current_user.organization_id).first()
        token = config.access_token if config else None
        waba = config.whatsapp_business_id if config else None
        
        meta_res = create_meta_template(
            name=template_in.name,
            category=template_in.category,
            language=template_in.language,
            components=template_in.components,
            token=token,
            waba_id=waba
        )
        if "error" in meta_res:
             error_msg = meta_res["error"]
             subcode = str(meta_res.get("subcode", ""))
             
             if subcode == "2388023":
                 error_msg = f"Template name lockout: {error_msg} (Error Code: 2388023). Meta does not allow reusing a name immediately after deletion. Please wait or use a different name."
             elif subcode == "2388024":
                 error_msg = f"Already Exists: {error_msg} (Error Code: 2388024). A template with this language already exists on Meta. Please click 'Sync Templates' or use a different name."
             
             raise HTTPException(status_code=400, detail=f"Meta Error: {error_msg}")
        
        meta_id = meta_res.get("id")
        status = "PENDING"

    new_template = WhatsAppTemplate(
        name=template_in.name,
        category=template_in.category,
        language=template_in.language,
        components=template_in.components,
        variable_mappings=template_in.variable_mappings,
        media_id=template_in.media_id,
        meta_template_id=meta_id,
        organization_id=current_user.organization_id, # Link to current user's organization
        status=status
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)

    log_action(
        db, "CREATE_TEMPLATE", "TEMPLATES", 
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
        organization_id=current_user.organization_id,
        details={"template_name": new_template.name, "category": new_template.category, "submit_to_meta": template_in.submit_to_meta},
        request=request
    )

    return new_template

@router.post("/sync")
def sync_templates(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_sync)
):
    """
    Sync all templates from Meta:
    - Updates status/rejection_reason for existing templates.
    - Imports brand new Meta templates not in local DB.
    - Removes local templates that no longer exist on Meta.
    """
    try:
        # Fetch Org Config
        config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == current_user.organization_id).first()
        token = config.access_token if config else None
        waba = config.whatsapp_business_id if config else None

        if not token or not waba:
            raise HTTPException(status_code=400, detail="Organization Meta credentials are not configured. Please set them in the Infrastructure settings.")

        meta_data = get_meta_templates_status(token=token, waba_id=waba)
        if "error" in meta_data:
            raise HTTPException(status_code=400, detail=meta_data["error"])

        meta_templates = meta_data.get("data", [])
        meta_names_on_server = {mt.get("name", "").lower() for mt in meta_templates}

        updated_count = 0
        imported_count = 0
        cleaned_count = 0

        # Step 1: Update or import templates FROM Meta
        for mt in meta_templates:
            slug = mt.get("name")
            status = mt.get("status")
            category = mt.get("category")
            language = mt.get("language")
            components = mt.get("components", [])
            meta_id = mt.get("id")

            # Search by meta_template_id first (most reliable), then by name+org
            local_tpl = db.query(WhatsAppTemplate).filter(
                WhatsAppTemplate.meta_template_id == meta_id
            ).first()

            if not local_tpl:
                local_tpl = db.query(WhatsAppTemplate).filter(
                    WhatsAppTemplate.name.ilike(slug),
                    WhatsAppTemplate.organization_id == current_user.organization_id
                ).first()

            if local_tpl:
                local_tpl.status = status
                local_tpl.rejection_reason = mt.get("rejection_reason")
                local_tpl.category = category
                local_tpl.language = language
                local_tpl.components = components
                local_tpl.meta_template_id = meta_id
                local_tpl.organization_id = current_user.organization_id  # Ensure org is set
                local_tpl.last_synced_at = datetime.now(timezone.utc)
                updated_count += 1
            else:
                # Check if a template with this name already exists (e.g., from another org without org_id)
                orphan = db.query(WhatsAppTemplate).filter(
                    WhatsAppTemplate.name.ilike(slug),
                    WhatsAppTemplate.organization_id == None
                ).first()

                if orphan:
                    # Adopt the orphan template into this org
                    orphan.status = status
                    orphan.rejection_reason = mt.get("rejection_reason")
                    orphan.category = category
                    orphan.language = language
                    orphan.components = components
                    orphan.meta_template_id = meta_id
                    orphan.organization_id = current_user.organization_id
                    orphan.last_synced_at = datetime.now(timezone.utc)
                    updated_count += 1
                else:
                    new_tpl = WhatsAppTemplate(
                        name=slug,
                        category=category,
                        language=language,
                        components=components,
                        status=status,
                        meta_template_id=meta_id,
                        organization_id=current_user.organization_id,  # Always set org
                        rejection_reason=mt.get("rejection_reason"),
                        last_synced_at=datetime.now(timezone.utc)
                    )
                    db.add(new_tpl)
                    imported_count += 1

        # Step 2: Remove local templates that no longer exist on Meta
        # (Skip LOCAL_ONLY — those are intentionally not on Meta)
        all_non_local = db.query(WhatsAppTemplate).filter(
            WhatsAppTemplate.status != "LOCAL_ONLY",
            WhatsAppTemplate.organization_id == current_user.organization_id
        ).all()
        for local_tpl in all_non_local:
            if local_tpl.name.lower() not in meta_names_on_server:
                db.delete(local_tpl)
                cleaned_count += 1

        db.commit()

        log_action(
            db, "SYNC_TEMPLATES", "TEMPLATES",
            user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
            organization_id=current_user.organization_id,
            details={"updated": updated_count, "imported": imported_count, "deleted": cleaned_count},
            request=request
        )

        return {
            "message": f"Sync complete: {updated_count} updated, {imported_count} imported, {cleaned_count} removed",
            "total_meta": len(meta_templates)
        }

    except HTTPException:
        raise  # Re-raise HTTP exceptions (they already have proper status codes)
    except Exception as e:
        db.rollback()
        logger.error(f"Template sync failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

@router.get("/")
def list_templates(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by status (e.g., APPROVED, PENDING)"),
    search: Optional[str] = Query(None, description="Search by template name"),
    category: Optional[str] = Query(None, description="Filter by category (MARKETING, UTILITY, AUTHENTICATION)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    current_user: Agent = Depends(require_view)
):
    query = db.query(WhatsAppTemplate)
    
    # Isolation: Filter by organization unless superadmin
    if not user_has_bypass(current_user):
        query = query.filter(WhatsAppTemplate.organization_id == current_user.organization_id)

    if status:
        query = query.filter(WhatsAppTemplate.status == status.upper())

    if category:
        query = query.filter(WhatsAppTemplate.category.ilike(category))


    if search:
        query = query.filter(WhatsAppTemplate.name.ilike(f"%{search}%"))

    total = query.count()
    
    # Sorting
    valid_columns = {
        "name": WhatsAppTemplate.name,
        "status": WhatsAppTemplate.status,
        "category": WhatsAppTemplate.category,
        "language": WhatsAppTemplate.language,
        "created_at": WhatsAppTemplate.created_at,
        "last_synced_at": WhatsAppTemplate.last_synced_at
    }
    
    target_col_name = sort_by if sort_by in valid_columns else "created_at"
    sort_col = valid_columns[target_col_name]
    
    if sort_order.lower() == "asc":
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    items = query.offset(skip).limit(limit).all()
    
    return {"total": total, "items": items}


class TemplateConfigure(BaseModel):
    variable_mappings: Optional[dict] = None
    media_id: Optional[str] = None

@router.post("/{template_id}/configure")
def configure_template(
    template_id: str,
    payload: TemplateConfigure,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    """
    Update local variable mappings and media_id for an existing template.
    Useful for templates synced from Meta or updating without re-approval.
    """
    # Convert string ID to UUID for SQLAlchemy
    try:
        id_uuid = uuid.UUID(template_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid template ID format")

    template = db.query(WhatsAppTemplate).get(id_uuid)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Isolation check
    verify_org_access(current_user, template.organization_id)
    
    logger.info(f"Configuring template {template.name} ({template_id})")
    template.variable_mappings = payload.variable_mappings
    template.media_id = payload.media_id
    db.commit()
    db.refresh(template)
    return template


@router.put("/{template_id}", summary="Edit Template (In-place Update)")
def update_template(
    template_id: uuid.UUID,
    template_in: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    """
    Logic:
    1. Check if in use by active campaign (BLOCK if yes)
    2. If template has a meta_template_id, update it on Meta
    3. If template is LOCAL_ONLY but submit_to_meta is True, create it on Meta
    4. Update local record
    """
    template = db.query(WhatsAppTemplate).get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Isolation check
    verify_org_access(current_user, template.organization_id)

    # 1. Block if used in active campaign
    if check_template_in_use(db, template.name):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit template '{template.name}' because it is in use by an ACTIVE campaign."
        )

    # 2. Validate: body must not end with a variable
    validate_template_body(template_in.components)

    meta_id = template.meta_template_id
    status = template.status
    
    # Fetch Org Config
    config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == template.organization_id).first()
    token = config.access_token if config else None
    waba = config.whatsapp_business_id if config else None

    # 3. Handle Meta Integration
    if template_in.submit_to_meta:
        is_missing_on_meta = False
        
        if meta_id:
            # UPDATE existing template on Meta
            meta_res = update_meta_template(
                template_id=meta_id,
                category=template_in.category,
                components=template_in.components,
                token=token
            )
            
            if "error" in meta_res:
                 meta_error = meta_res.get("error", "").lower()
                 meta_code = str(meta_res.get("code", ""))
                 meta_subcode = str(meta_res.get("subcode", ""))
                 
                 # 1. Check if the error is specifically "Object does not exist" (Subcode 33)
                 # This is the ONLY case where we fallback to creation.
                 if meta_subcode == "33":
                      logger.warning(f"Template ID {meta_id} not found on Meta. Falling back to creation.")
                      is_missing_on_meta = True
                 # 2. Handle specific policy errors that should BLOCK creation
                 elif meta_subcode == "2388094":
                      raise HTTPException(
                          status_code=400, 
                          detail="Meta Policy Error: Sample templates (like 'hello_world') cannot be edited or deleted. Please create a NEW template with a different name."
                      )
                 # 3. Handle other errors
                 else:
                      raise HTTPException(status_code=400, detail=f"Meta Update Error: {meta_res['error']}")
            else:
                 # Success
                 status = "PENDING"
        
        # If it was never on Meta OR it's missing (is_missing_on_meta), we CREATE it
        if not meta_id or is_missing_on_meta:
            # CREATE new template on Meta
            meta_res = create_meta_template(
                name=template_in.name,
                category=template_in.category,
                language=template_in.language,
                components=template_in.components,
                token=token,
                waba_id=waba
            )
            if "error" in meta_res:
                 error_msg = meta_res["error"]
                 subcode = str(meta_res.get("subcode", ""))
                 
                 if subcode == "2388023":
                     error_msg = f"Template name lockout: {error_msg} (Error Code: 2388023). Meta does not allow reusing a name immediately after deletion. Please wait or use a different name."
                 elif subcode == "2388024":
                     error_msg = f"Already Exists: {error_msg} (Error Code: 2388024). Meta already has a template with this name. Please click 'Sync Templates' or use a different name."
                 
                 raise HTTPException(status_code=400, detail=f"Meta Creation Error: {error_msg}")
            
            meta_id = meta_res.get("id")
            status = "PENDING"


    # 4. Update local record
    template.name = template_in.name
    template.category = template_in.category
    template.language = template_in.language
    template.components = template_in.components
    template.variable_mappings = template_in.variable_mappings
    template.media_id = template_in.media_id
    template.meta_template_id = meta_id
    template.status = status
    template.last_synced_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(template)
    return template


@router.get("/{template_id}")
def get_template(
    template_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_view)
):
    template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
        
    # Isolation check
    verify_org_access(current_user, template.organization_id)
        
    return template


@router.delete("/{template_id}")
def delete_template(
    template_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    try:
        logger.info(f"DELETE_TEMPLATE_START: Received request to delete template ID: {template_id}")
        template = db.query(WhatsAppTemplate).get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Isolation check
        verify_org_access(current_user, template.organization_id)

        # Capture name before deletion to avoid DetachedInstanceError after commit
        template_name = template.name

        # SAFETY CHECK: Block deletion if used in active campaigns
        if check_template_in_use(db, template_name):
            raise HTTPException(
                status_code=400, 
                detail=f"Template '{template_name}' is currently being used in an ACTIVE campaign (Running/Scheduled). Please stop or complete the campaign before deleting."
            )

        # Try to delete from Meta if it was ever submitted (not LOCAL_ONLY)
        if template.status != "LOCAL_ONLY":
            # Fetch Org Config
            config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == current_user.organization_id).first()
            token = config.access_token if config else None
            waba = config.whatsapp_business_id if config else None

            meta_res = delete_meta_template(template_name, language=template.language, token=token, waba_id=waba)

            if "error" in meta_res:
                meta_error = meta_res.get("error", "").lower()
                meta_code = str(meta_res.get("code", ""))
                status_code = meta_res.get("status", 0)

                # If Meta says it's already gone — that's fine, clean up locally
                is_already_gone = (
                    "not found" in meta_error or
                    "does not exist" in meta_error or
                    "doesn't exist" in meta_error or
                    "invalid parameter" in meta_error or
                    meta_code == "100" or
                    meta_code == "200" or
                    status_code == 404
                )

                if is_already_gone:
                    # Template was already deleted on Meta — just clean local record
                    pass
                else:
                    # Meta actively refused the deletion (e.g. template in use by a campaign)
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Could not delete template from Meta: {meta_res.get('error')}. "
                            "The template was NOT deleted locally either. "
                            "If it is in use by an active campaign, stop the campaign first."
                        )
                    )

        # Hard delete: remove from local DB
        db.delete(template)
        db.commit()

        log_action(
            db, "DELETE_TEMPLATE", "TEMPLATES", 
            user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
            organization_id=current_user.organization_id,
            details={"template_name": template_name},
            request=request
        )

        return {"message": f"Template '{template_name}' deleted successfully from Meta and local database."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error during deletion: {str(e)}")

@router.post("/upload-media")
async def upload_template_media(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    """
    Handle local file upload for Template Header examples.
    Uploads the file to Meta's Resumable Upload API and returns the handle 'h'.
    """
    try:
        content = await file.read()
        file_size = len(content)
        file_name = file.filename
        file_type = file.content_type

        # 0. Local Validation (Rule: Early Failure)
        size_mb = round(file_size / (1024 * 1024), 2)
        if file_type.startswith("image/"):
            if file_size > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"Image too large ({size_mb}MB). Meta allows a maximum of 5MB for images. Please compress your image and try again.")
        elif file_type.startswith("video/"):
            if file_size > 16 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"Video too large ({size_mb}MB). Meta allows a maximum of 16MB for videos. Please use a shorter or lower resolution video.")
        elif file_type.startswith("audio/"):
            if file_size > 16 * 1024 * 1024:
                raise HTTPException(status_code=400, detail=f"Audio too large ({size_mb}MB). Meta allows a maximum of 16MB for audio files.")
        elif file_size > 100 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File too large ({size_mb}MB). WhatsApp Cloud API supports a maximum of 100MB per file.")

        # Fetch Org Config for credentials
        config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == current_user.organization_id).first()
        token = config.access_token if config else None
        app_id = config.meta_app_id if config else None

        if not token or not app_id:
            raise HTTPException(status_code=400, detail="Organization Meta credentials not configured. Please set App ID and Access Token.")

        # 1. Start Session
        session_res = create_resumable_upload_session(file_name, file_size, file_type, token=token, app_id=app_id)
        if "error" in session_res:
            error_msg = session_res["error"]
            # Handle specific MIME mismatch error if Meta returns it early
            if "131053" in str(error_msg) or "mimetype" in str(error_msg).lower():
                error_msg = f"MIME Type Mismatch: Meta rejected the file '{file_name}' because its content doesn't match its extension ({file_type})."
            raise HTTPException(status_code=400, detail=error_msg)
        
        session_id = session_res.get("id")
        if not session_id:
            raise HTTPException(status_code=400, detail="Failed to create Meta upload session")

        # 2. Upload Content
        upload_res = upload_file_content(session_id, content, token=token)
        if "error" in upload_res:
             raise HTTPException(status_code=400, detail=upload_res["error"])
        
        handle = upload_res.get("h")
        if not handle:
            raise HTTPException(status_code=400, detail="Meta did not return a valid media handle")

        return {"handle": handle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
