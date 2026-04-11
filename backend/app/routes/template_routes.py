from fastapi import APIRouter, Depends, HTTPException, Body, Query, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.template import WhatsAppTemplate
from pydantic import BaseModel
from typing import List, Optional
from app.services.meta_api import create_meta_template, get_meta_templates_status, create_resumable_upload_session, upload_file_content, delete_meta_template
from datetime import datetime
import uuid
import logging
from app.core.security import get_current_user, RoleChecker
from app.models.agent import Agent
from app.models.campaign import Campaign

logger = logging.getLogger("adcom-api")

# Access control workers
admin_only = RoleChecker(["admin"])
any_agent = get_current_user

router = APIRouter(prefix="/templates", tags=["Templates"])

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
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    existing = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == template_in.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Template name already exists")
    
    meta_id = None
    status = "LOCAL_ONLY"
    
    if template_in.submit_to_meta:
        meta_res = create_meta_template(
            name=template_in.name,
            category=template_in.category,
            language=template_in.language,
            components=template_in.components
        )
        if "error" in meta_res:
             raise HTTPException(status_code=400, detail=f"Meta Error: {meta_res['error']}")
        
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
        status=status
    )
    db.add(new_template)
    db.commit()
    db.refresh(new_template)
    return new_template

@router.post("/sync")
def sync_templates(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    """
    Sync all templates from Meta:
    - Updates status/rejection_reason for existing templates.
    - Imports brand new Meta templates not in local DB.
    - Removes local templates that no longer exist on Meta.
    """
    meta_data = get_meta_templates_status()
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

        local_tpl = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name.ilike(slug)).first()

        if local_tpl:
            local_tpl.status = status
            local_tpl.rejection_reason = mt.get("rejection_reason")
            local_tpl.category = category
            local_tpl.language = language
            local_tpl.components = components
            local_tpl.meta_template_id = meta_id
            local_tpl.last_synced_at = datetime.utcnow()
            updated_count += 1
        else:
            new_tpl = WhatsAppTemplate(
                name=slug,
                category=category,
                language=language,
                components=components,
                status=status,
                meta_template_id=meta_id,
                rejection_reason=mt.get("rejection_reason"),
                last_synced_at=datetime.utcnow()
            )
            db.add(new_tpl)
            imported_count += 1

    # Step 2: Remove local templates that no longer exist on Meta
    # (Skip LOCAL_ONLY — those are intentionally not on Meta)
    all_non_local = db.query(WhatsAppTemplate).filter(
        WhatsAppTemplate.status != "LOCAL_ONLY"
    ).all()
    for local_tpl in all_non_local:
        if local_tpl.name.lower() not in meta_names_on_server:
            db.delete(local_tpl)
            cleaned_count += 1

    db.commit()
    return {
        "message": f"Sync complete: {updated_count} updated, {imported_count} imported, {cleaned_count} removed",
        "total_meta": len(meta_templates)
    }

@router.get("/")
def list_templates(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None, description="Filter by status (e.g., APPROVED, PENDING)"),
    search: Optional[str] = Query(None, description="Search by template name"),
    current_user: Agent = Depends(any_agent)
):
    query = db.query(WhatsAppTemplate)

    if status:
        query = query.filter(WhatsAppTemplate.status == status.upper())

    if search:
        query = query.filter(WhatsAppTemplate.name.ilike(f"%{search}%"))

    return query.all()

class TemplateConfigure(BaseModel):
    variable_mappings: Optional[dict] = None
    media_id: Optional[str] = None

@router.post("/{template_id}/configure")
def configure_template(
    template_id: str,
    payload: TemplateConfigure,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
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
    
    logger.info(f"Configuring template {template.name} ({template_id})")
    template.variable_mappings = payload.variable_mappings
    template.media_id = payload.media_id
    db.commit()
    db.refresh(template)
    return template


@router.put("/{template_id}", summary="Edit Template (Delete + Recreate Logic)")
def update_template(
    template_id: uuid.UUID,
    template_in: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    """
    Logic:
    1. Check for name changes (not supported yet or requires separate logic)
    2. Check if in use by active campaign (BLOCK if yes)
    3. Delete old one from Meta
    4. Re-create new one on Meta
    5. Update local record
    """
    template = db.query(WhatsAppTemplate).get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 1. Block if used in active campaign
    if check_template_in_use(db, template.name):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit template '{template.name}' because it is in use by an ACTIVE campaign."
        )

    # 2. Delete from Meta if applicable
    if template.status != "LOCAL_ONLY":
        delete_meta_template(template.name, language=template.language)

    # 3. Create fresh version on Meta
    meta_id = None
    status = "LOCAL_ONLY"
    
    if template_in.submit_to_meta:
        meta_res = create_meta_template(
            name=template_in.name,
            category=template_in.category,
            language=template_in.language,
            components=template_in.components
        )
        if "error" in meta_res:
             raise HTTPException(status_code=400, detail=f"Meta Error: {meta_res['error']}")
        
        meta_id = meta_res.get("id")
        status = "PENDING"

    # 4. Update existing local record
    template.name = template_in.name
    template.category = template_in.category
    template.language = template_in.language
    template.components = template_in.components
    template.variable_mappings = template_in.variable_mappings
    template.media_id = template_in.media_id
    template.meta_template_id = meta_id
    template.status = status
    template.last_synced_at = datetime.utcnow()

    db.commit()
    db.refresh(template)
    return template

@router.get("/{template_id}")
def get_template(
    template_id: uuid.UUID, 
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    template = db.query(WhatsAppTemplate).get(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/{template_id}")
def delete_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    try:
        logger.info(f"DELETE_TEMPLATE_START: Received request to delete template ID: {template_id}")
        template = db.query(WhatsAppTemplate).get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

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
            meta_res = delete_meta_template(template_name, language=template.language)

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
        return {"message": f"Template '{template_name}' deleted successfully from Meta and local database."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template {template_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal Server Error during deletion: {str(e)}")

@router.post("/upload-media")
async def upload_template_media(
    file: UploadFile = File(...),
    current_user: Agent = Depends(any_agent)
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

        # 1. Start Session
        session_res = create_resumable_upload_session(file_name, file_size, file_type)
        if "error" in session_res:
            raise HTTPException(status_code=400, detail=session_res["error"])
        
        session_id = session_res.get("id")
        if not session_id:
            raise HTTPException(status_code=400, detail="Failed to create Meta upload session")

        # 2. Upload Content
        upload_res = upload_file_content(session_id, content)
        if "error" in upload_res:
             raise HTTPException(status_code=400, detail=upload_res["error"])
        
        handle = upload_res.get("h")
        if not handle:
            raise HTTPException(status_code=400, detail="Meta did not return a valid media handle")

        return {"handle": handle}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
