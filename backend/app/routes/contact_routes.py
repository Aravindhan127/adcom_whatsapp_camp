import csv
import io
import json
import uuid
import re
from datetime import datetime, date, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.core.database import get_db, logger
from app.models.contact import Contact, ContactList, ImportHistory, ContactStatus, ContactSource, ImportStatus
from app.models.organization import ContactFieldConfig
from app.core.security import get_current_user, RoleChecker, verify_org_access, PermissionChecker, user_has_bypass
from app.models.agent import Agent
from app.services.audit_service import log_action
from fastapi import Request

# Access control workers
require_view = PermissionChecker("contact.view")
require_manage = PermissionChecker("contact.manage")
require_import = PermissionChecker("contact.import")
require_delete = PermissionChecker("contact.delete")
admin_only = PermissionChecker("org.manage")
any_agent = get_current_user

# Pre-defined list of common date formats for robust parsing
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    
    # Already a datetime or date object
    if isinstance(date_str, (datetime, date)):
        return date_str

    clean_date = str(date_str).strip()
    if not clean_date:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(clean_date, fmt)
        except ValueError:
            continue
    
    # If all formats fail, return None instead of crashing
    return None

def sanitize_excel_phone(val):
    """Converts numeric/scientific notation values from Excel/CSV to clean strings."""
    if val is None: return ""
    # Handle direct numeric types (float/int)
    if isinstance(val, (int, float)):
        return "{:.0f}".format(val)
    
    # Handle string scientific notation (e.g. '9.19E+11')
    s_val = str(val).strip()
    if 'E+' in s_val.upper():
        try:
            return "{:.0f}".format(float(s_val))
        except:
            pass
    return s_val
    
class FieldConfigCreate(BaseModel):
    field_name: str
    field_label: str
    field_type: str = "text"
    is_required: bool = False
    options: Optional[List[str]] = None

router = APIRouter(prefix="/contacts", tags=["Contacts Management"])

def validate_phone_number(phone: str) -> tuple[bool, str, str, str]:
    if not phone: return False, "", "", "Empty"
    # Strict digits-only with leading +
    cleaned = re.sub(r'[^\d]', '', str(phone).strip())

    # E.164 format requires 10-15 digits (excluding the +)
    if len(cleaned) < 10 or len(cleaned) > 15:
        return False, cleaned, "", "Invalid length"

    # Prepend + if missing (E.164 format)
    final = f"+{cleaned}"

    # Extract country code more intelligently
    # Most country codes are 1-3 digits, with +1 for US/CA, +44 for UK, +91 for India, etc.
    if len(cleaned) == 10:  # Assume US/CA format without country code
        country_code = "1"
        final = f"+1{cleaned}"
    elif len(cleaned) == 11 and cleaned.startswith("1"):  # US/CA with country code
        country_code = "1"
    else:
        # Extract country code based on common patterns
        # This is a heuristic - production should use libphonenumber
        if cleaned.startswith("1") and len(cleaned) == 11:
            country_code = "1"
        elif cleaned.startswith("44"):
            country_code = "44"
        elif cleaned.startswith("91"):
            country_code = "91"
        elif cleaned.startswith("86"):
            country_code = "86"
        elif cleaned.startswith("49"):
            country_code = "49"
        else:
            # Default: take first 1-2 digits
            country_code = cleaned[:2] if len(cleaned) > 10 else cleaned[:1]

    return True, final, country_code, ""

def normalize_phone(phone: str) -> str:
    # Digits only for uniqueness check
    return re.sub(r'\D', '', phone)

@router.post("/bulk-import", summary="Bulk Import Contacts")
async def bulk_import_contacts(
    request: Request,
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = Form(None),
    list_id: Optional[uuid.UUID] = Form(None),
    field_mapping: Optional[str] = Form(None),
    upsert: bool = Form(False),
    organization_id: Optional[uuid.UUID] = Form(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_import)
):
    # Isolation Logic: Determine which org this import belongs to
    target_org_id = organization_id or current_user.organization_id
    if not target_org_id:
        raise HTTPException(status_code=400, detail="Organization ID is required")

    # SECURITY: Only Super Admin can specify an org different from their own
    if organization_id and organization_id != current_user.organization_id:
        if not user_has_bypass(current_user):
            raise HTTPException(status_code=403, detail="Not authorized to import for other organizations")
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.xls') or filename.endswith('.xlx')):
        raise HTTPException(400, "Only CSV and Excel (.xlsx, .xls, .xlx) supported")
    
    file_type = 'csv' if filename.endswith('.csv') else 'xlsx'
    if filename.endswith('.xls'):
        file_type = 'xls'
    elif filename.endswith('.xlx'):
        file_type = 'xlx'
    
    import_record = ImportHistory(
        filename=file.filename, file_type=file_type,
        uploaded_by=current_user.username, status=ImportStatus.PROCESSING.value,
        organization_id=target_org_id # Track which org imported this
    )
    db.add(import_record)
    db.commit()
    db.refresh(import_record)
    
    try:
        content = await file.read()
        rows = []
        if file_type == 'csv':
            decoded = content.decode('utf-8', errors='ignore')
            rows = list(csv.DictReader(io.StringIO(decoded)))
        elif file_type == 'xls':
            try:
                import xlrd
            except ImportError:
                raise HTTPException(status_code=500, detail="xlrd library is required to parse .xls files. Please install it (e.g., run 'pip install xlrd').")
            wb = xlrd.open_workbook(file_contents=content)
            sheet = wb.sheet_by_index(0)
            headers = [str(x).lower().strip() for x in sheet.row_values(0)]
            rows = [dict(zip(headers, sheet.row_values(rx))) for rx in range(1, sheet.nrows) if any(sheet.row_values(rx))]
        else:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            sheet = wb.active
            headers = [str(c.value).lower().strip() for c in sheet[1]]
            rows = [dict(zip(headers, row)) for row in sheet.iter_rows(min_row=2, values_only=True) if any(row)]
            wb.close()
        
        # 2. Parse field mapping if provided
        mapping = {}
        if field_mapping:
            try:
                mapping = json.loads(field_mapping)
            except:
                logger.warning("Invalid field_mapping JSON provided, falling back to auto-detect")

        # 3. Process Rows
        import_record.records_count = len(rows)
        
        # Batch-check for existing numbers to avoid loading entire DB
        incoming_numbers = []
        for row in rows:
            # Use mapping or fallback to common names
            phone_col = mapping.get('phone_number')
            phone = row.get(phone_col) if phone_col else (row.get('phone_number') or row.get('phone') or row.get('mobile'))
            phone = sanitize_excel_phone(phone)
            
            if phone:
                is_valid, cleaned, _, _ = validate_phone_number(phone)
                if is_valid:
                    incoming_numbers.append(normalize_phone(cleaned))
        
        # Get existing normalized numbers that match our incoming batch (limit to 100 for SQL safety)
        existing_in_db_map = {}
        unique_incoming = list(set(incoming_numbers))
        if unique_incoming:
            # Filter by organization to avoid leakage
            existing_contacts = db.query(Contact).filter(
                Contact.organization_id == target_org_id,
                or_(*[Contact.phone_number.like(f"%{num}") for num in unique_incoming[:100]])
            ).all()
            existing_in_db_map = {normalize_phone(c.phone_number): c for c in existing_contacts}

        success, updated = 0, 0
        duplicate_details = [] # List of {"phone": str, "name": str}
        invalid_details = []
        contacts_to_create = []
        seen_in_batch = set()
        
        for row in rows:
            # Resolve fields using mapping
            phone_col = mapping.get('phone_number')
            name_col = mapping.get('name')
            
            phone = row.get(phone_col) if phone_col else (row.get('phone_number') or row.get('phone') or row.get('mobile'))
            phone = sanitize_excel_phone(phone)
            name = row.get(name_col) if name_col else (row.get('name') or row.get('full_name'))
            
            if not phone:
                invalid_details.append({"row": rows.index(row) + 2, "error": "Missing phone number"})
                continue
            
            is_valid, cleaned, cc, err = validate_phone_number(phone)
            if not is_valid:
                invalid_details.append({"phone": str(phone), "error": err or "Invalid format"})
                continue
                
            norm = normalize_phone(cleaned)
            
            if norm in seen_in_batch:
                duplicate_details.append({"phone": cleaned, "name": name})
                continue
            seen_in_batch.add(norm)

            # Utility to get value from row based on mapping or fallbacks
            def get_row_val(key, fallbacks):
                col = mapping.get(key)
                if col and col in row: return row[col]
                for f in fallbacks:
                    if f in row: return row[f]
                return None

            # 4. Handle Custom Fields Mapping (Rule: Admin/SuperAdmin Configured)
            # Identify which mapping keys are 'custom' (not in standard model fields)
            standard_keys = ['phone_number', 'name', 'company_name', 'lead_source', 'date_of_birth', 'customer_category', 'customer_stage', 'city', 'product_service_interest', 'consent_confirmation']
            
            def get_custom_data(row_dict, mapping_dict):
                data = {}
                # Logic A: Explicitly mapped custom fields
                for target_field, excel_col in mapping_dict.items():
                    if target_field not in standard_keys and excel_col in row_dict:
                        data[target_field] = row_dict[excel_col]
                
                # Logic B: Auto-detect (If not explicitly mapped, check for common names matching standard keys)
                # This is already handled by Logic A if mapping is correct, but let's keep it robust.
                return data

            if norm in existing_in_db_map:
                if upsert:
                    existing_contact = existing_in_db_map[norm]
                    if name: existing_contact.name = name
                    if list_id: existing_contact.list_id = list_id
                    
                    existing_contact.company_name = get_row_val('company_name', ['company_name', 'company']) or existing_contact.company_name
                    existing_contact.lead_source = get_row_val('lead_source', ['lead_source', 'source']) or existing_contact.lead_source
                    dob_raw = get_row_val('date_of_birth', ['date_of_birth', 'dob'])
                    if dob_raw:
                        existing_contact.date_of_birth = parse_date(dob_raw)
                    existing_contact.customer_category = get_row_val('customer_category', ['customer_category', 'type']) or existing_contact.customer_category
                    existing_contact.customer_stage = get_row_val('customer_stage', ['customer_stage', 'stage']) or existing_contact.customer_stage
                    existing_contact.city = get_row_val('city', ['city']) or existing_contact.city
                    existing_contact.product_service_interest = get_row_val('product_service_interest', ['product_service_interest', 'interest']) or existing_contact.product_service_interest
                    existing_contact.consent_confirmation = get_row_val('consent_confirmation', ['consent_confirmation', 'consent']) or existing_contact.consent_confirmation
                    
                    # Update Custom Fields on Upsert
                    new_custom = get_custom_data(row, mapping)
                    if new_custom:
                        if not existing_contact.custom_fields:
                            existing_contact.custom_fields = {}
                        existing_contact.custom_fields.update(new_custom)
                    
                    updated += 1
                else:
                    duplicate_details.append({"phone": cleaned, "name": name})
                continue

            contacts_to_create.append(Contact(
                phone_number=cleaned, 
                name=name, 
                country_code=cc,
                organization_id=target_org_id,
                source=file_type, 
                list_id=list_id,
                import_id=import_record.id,
                # Fields from mapping logic
                company_name=get_row_val('company_name', ['company_name', 'company']),
                lead_source=get_row_val('lead_source', ['lead_source', 'source']),
                date_of_birth=parse_date(get_row_val('date_of_birth', ['date_of_birth', 'dob'])),
                customer_category=get_row_val('customer_category', ['customer_category', 'type']),
                customer_stage=get_row_val('customer_stage', ['customer_stage', 'stage']),
                city=get_row_val('city', ['city']),
                product_service_interest=get_row_val('product_service_interest', ['product_service_interest', 'interest']),
                consent_confirmation=get_row_val('consent_confirmation', ['consent_confirmation', 'consent']),
                custom_fields=get_custom_data(row, mapping) # Store mapped dynamic data
            ))
            success += 1
        
        if contacts_to_create:
            db.bulk_save_objects(contacts_to_create)
        
        db.commit()
        
        # Summary for DB
        summary = {
            "success": success,
            "updated": updated,
            "duplicates": len(duplicate_details),
            "invalid": len(invalid_details),
            "duplicate_list": duplicate_details[:100], # Cap for DB storage
            "invalid_list": invalid_details[:100]
        }
        
        import_record.success_count = success
        import_record.duplicate_count = len(duplicate_details)
        import_record.failed_count = len(invalid_details)
        import_record.error_details = json.dumps(summary)
        import_record.status = ImportStatus.COMPLETED.value
        import_record.completed_at = datetime.now(timezone.utc)
        db.commit()
        
        log_action(
            db, "BULK_IMPORT", "CONTACTS", 
            user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
            organization_id=target_org_id,
            details={"filename": file.filename, "success": success, "updated": updated, "total": len(rows)},
            request=request
        )

        return {
            "message": "Import completed", 
            "import_id": str(import_record.id), 
            "success": success, 
            "duplicates": len(duplicate_details), 
            "duplicate_list": duplicate_details,
            "updated": updated,
            "invalid": len(invalid_details),
            "invalid_list": invalid_details,
            "uploaded_by": current_user.username
        }
    except Exception as e:
        db.rollback()
        import_record.status = ImportStatus.FAILED.value
        import_record.error_details = str(e)
        db.commit()
        raise HTTPException(500, f"Import failed: {str(e)}")

class ContactCreate(BaseModel):
    phone_number: str
    name: Optional[str] = None
    list_id: Optional[uuid.UUID] = None
    upsert: Optional[bool] = False
    organization_id: Optional[uuid.UUID] = None
    
    # New Fields
    company_name: Optional[str] = None
    lead_source: Optional[str] = None
    date_of_birth: Optional[str] = None # Will parse to datetime
    customer_category: Optional[str] = None
    customer_stage: Optional[str] = None
    city: Optional[str] = None
    product_service_interest: Optional[str] = None
    consent_confirmation: Optional[str] = None
    
    # Dynamic Data
    custom_fields: Optional[dict] = None

@router.post("/", summary="Create Single Contact")
async def create_contact(
    contact: ContactCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    is_valid, cleaned, cc, err = validate_phone_number(contact.phone_number)
    if not is_valid:
        raise HTTPException(400, f"Invalid phone number: {err}")
    
    norm = normalize_phone(cleaned)
    # Isolation Logic: Determine which org this contact belongs to
    target_org_id = contact.organization_id or current_user.organization_id
    if not target_org_id:
        raise HTTPException(status_code=400, detail="Organization ID is required. Please select one.")

    # SECURITY: Only Super Admin can specify an org different from their own
    if contact.organization_id and contact.organization_id != current_user.organization_id:
        if not (current_user.role_obj.can_bypass_isolation if current_user.role_obj else current_user.role == "superadmin"):
            raise HTTPException(status_code=403, detail="Not authorized to create contacts for other organizations")

    # Strict duplicate check using normalized number within the target org
    query = db.query(Contact).filter(
        Contact.organization_id == target_org_id,
        or_(
            Contact.phone_number == cleaned,
            Contact.phone_number == norm,
            Contact.phone_number == f"+{norm}"
        )
    )
    existing = query.first()
    
    if existing:
        if contact.upsert:
            if contact.name: existing.name = contact.name
            if contact.list_id: existing.list_id = contact.list_id
            
            # Update New Fields
            if contact.company_name: existing.company_name = contact.company_name
            if contact.lead_source: existing.lead_source = contact.lead_source
            if contact.date_of_birth: existing.date_of_birth = parse_date(contact.date_of_birth)
            if contact.customer_category: existing.customer_category = contact.customer_category
            if contact.customer_stage: existing.customer_stage = contact.customer_stage
            if contact.city: existing.city = contact.city
            if contact.product_service_interest: existing.product_service_interest = contact.product_service_interest
            if contact.consent_confirmation: existing.consent_confirmation = contact.consent_confirmation
            
            # Update Dynamic Fields (Merge existing with new)
            if contact.custom_fields:
                if not existing.custom_fields:
                    existing.custom_fields = {}
                existing.custom_fields.update(contact.custom_fields)
            
            db.commit()
            db.refresh(existing)
            return existing
        else:
            raise HTTPException(400, f"This number ({cleaned}) already exists in this organization.")

    # Validate Required Dynamic Fields
    custom_fields_data = contact.custom_fields or {}
    field_configs = db.query(ContactFieldConfig).filter(ContactFieldConfig.organization_id == target_org_id).all()
    for config in field_configs:
        if config.is_required and not custom_fields_data.get(config.field_name):
            raise HTTPException(status_code=400, detail=f"The field '{config.field_label}' is required for this organization.")

    new_contact = Contact(
        phone_number=cleaned,
        name=contact.name,
        country_code=cc,
        source=ContactSource.MANUAL.value,
        list_id=contact.list_id,
        organization_id=target_org_id,
        # New Fields
        company_name=contact.company_name,
        lead_source=contact.lead_source,
        date_of_birth=parse_date(contact.date_of_birth),
        customer_category=contact.customer_category,
        customer_stage=contact.customer_stage,
        city=contact.city,
        product_service_interest=contact.product_service_interest,
        consent_confirmation=contact.consent_confirmation,
        custom_fields=contact.custom_fields
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)

    log_action(
        db, "CREATE_CONTACT", "CONTACTS", 
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
        organization_id=current_user.organization_id,
        details={"phone": cleaned, "name": contact.name},
        request=request
    )

    return new_contact

@router.get("/filter-options", summary="Get Unique Values for Contact Filters")
async def get_contact_filter_options(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_view)
):
    """Returns unique values for categories, stages, cities, and sources to populate UI filters."""
    categories = db.query(Contact.customer_category).filter(Contact.customer_category != None).distinct().all()
    stages = db.query(Contact.customer_stage).filter(Contact.customer_stage != None).distinct().all()
    cities = db.query(Contact.city).filter(Contact.city != None).distinct().all()
    sources = db.query(Contact.lead_source).filter(Contact.lead_source != None).distinct().all()

    return {
        "categories": [c[0] for c in categories],
        "stages": [s[0] for s in stages],
        "cities": [ct[0] for ct in cities],
        "sources": [src[0] for src in sources]
    }

@router.get("/config/fields", summary="Get Organization Custom Fields")
async def get_org_field_config(
    org_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_view)
):
    target_org_id = org_id or current_user.organization_id
    if not target_org_id:
        return []
    
    # SECURITY: Verify access if fetching for another org
    if org_id and org_id != current_user.organization_id:
        if not (current_user.role_obj.can_bypass_isolation if current_user.role_obj else current_user.role == "superadmin"):
            raise HTTPException(status_code=403, detail="Not authorized to view other organization fields")
            
    fields = db.query(ContactFieldConfig).filter(ContactFieldConfig.organization_id == target_org_id).all()
    return fields

@router.post("/config/fields", summary="Add Organization Custom Field")
async def add_org_field_config(
    field_in: FieldConfigCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(PermissionChecker("system.manage")) # Restricted to System/Super Admin
):
    # Rule: Field names should be alphanumeric and lowercase for JSON consistency
    safe_name = re.sub(r'[^a-z0-9_]', '', field_in.field_name.lower())
    
    existing = db.query(ContactFieldConfig).filter(
        ContactFieldConfig.organization_id == current_user.organization_id,
        ContactFieldConfig.field_name == safe_name
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="A field with this name already exists")
        
    new_field = ContactFieldConfig(
        organization_id=current_user.organization_id,
        field_name=safe_name,
        field_label=field_in.field_label,
        field_type=field_in.field_type,
        is_required=field_in.is_required,
        options=field_in.options
    )
    db.add(new_field)
    db.commit()
    db.refresh(new_field)
    return new_field

@router.get("/", summary="List Contacts with Filters")
async def list_contacts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    list_id: Optional[uuid.UUID] = Query(None),
    company_name: Optional[str] = Query(None),
    lead_source: Optional[str] = Query(None),
    customer_category: Optional[str] = Query(None),
    customer_stage: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_view)
):
    try:
        query = db.query(Contact)
        
        # Isolation: Filter by organization unless superadmin
        if not (current_user.role_obj.can_bypass_isolation if current_user.role_obj else current_user.role == "superadmin"):
            query = query.filter(Contact.organization_id == current_user.organization_id)
        
        # 1. Search (Name/Phone)
        # 1. Search Logic
        print(f"DEBUG: Fetching contacts | search: {search} | stage: {customer_stage} | category: {customer_category}")
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Contact.name.ilike(search_term),
                    Contact.phone_number.ilike(search_term),
                    Contact.company_name.ilike(search_term),
                    Contact.city.ilike(search_term)
                )
            )
        
        # 2. Filters
        if status:
            query = query.filter(Contact.status == status)
        if list_id:
            query = query.filter(Contact.list_id == list_id)
        if company_name:
            query = query.filter(Contact.company_name.ilike(f"%{company_name}%"))
        if lead_source:
            query = query.filter(Contact.lead_source == lead_source)
        if customer_category:
            query = query.filter(Contact.customer_category == customer_category)
        if customer_stage:
            query = query.filter(Contact.customer_stage == customer_stage)
        if city:
            query = query.filter(Contact.city.ilike(f"%{city}%"))
        
        # 3. Total Count (before pagination)
        total = query.count()
        print(f"DEBUG: Found {total} total contacts matching criteria")
        
        # 4. Sorting
        valid_columns = {
            "name": Contact.name,
            "phone_number": Contact.phone_number,
            "created_at": Contact.created_at,
            "company_name": Contact.company_name,
            "city": Contact.city,
            "customer_category": Contact.customer_category,
            "customer_stage": Contact.customer_stage,
            "lead_source": Contact.lead_source,
            "date_of_birth": Contact.date_of_birth,
            "product_service_interest": Contact.product_service_interest,
            "consent_confirmation": Contact.consent_confirmation
        }
        
        # Safe column resolution
        target_col_name = sort_by if sort_by in valid_columns else "created_at"
        sort_col = valid_columns[target_col_name]
        
        if sort_order.lower() == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())
            
        # 5. Paginate
        items = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "items": items,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Query Error: {str(e)}. Please check if your database is accessible.")

class BulkActionRequest(BaseModel):
    contact_ids: List[uuid.UUID]
    action: str # 'delete', 'update_status', 'update_customer_category'
    value: Optional[str] = None

@router.post("/bulk-action", summary="Handle Bulk Contact Actions")
async def bulk_contact_action(
    request_payload: BulkActionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_delete)
):
    query = db.query(Contact).filter(Contact.id.in_(request_payload.contact_ids))
    
    # Isolation: Apply organization filter
    if not (current_user.role_obj.can_bypass_isolation if current_user.role_obj else current_user.role == "superadmin"):
        query = query.filter(Contact.organization_id == current_user.organization_id)
    
    if request_payload.action == "delete":
        count = query.delete(synchronize_session=False)
        db.commit()

        log_action(
            db, "BULK_DELETE_CONTACTS", "CONTACTS", 
            user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
            organization_id=current_user.organization_id,
            details={"count": count},
            request=request
        )

        return {"message": f"Successfully deleted {count} contacts"}
    
    elif request_payload.action == "update_status":
        if not request_payload.value:
            raise HTTPException(status_code=400, detail="Status value required")
        count = query.update({"status": request_payload.value}, synchronize_session=False)
        db.commit()
        return {"message": f"Successfully updated status for {count} contacts"}
    
    elif request_payload.action == "update_customer_category":
        if not request_payload.value:
            raise HTTPException(status_code=400, detail="Category value required")
        count = query.update({"customer_category": request_payload.value}, synchronize_session=False)
        db.commit()
        return {"message": f"Successfully updated customer category for {count} contacts"}
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported action")


class ContactUpdate(BaseModel):
    phone_number: Optional[str] = None
    name: Optional[str] = None
    list_id: Optional[uuid.UUID] = None
    status: Optional[str] = None

    # New Fields
    company_name: Optional[str] = None
    lead_source: Optional[str] = None
    date_of_birth: Optional[str] = None
    customer_category: Optional[str] = None
    customer_stage: Optional[str] = None
    city: Optional[str] = None
    product_service_interest: Optional[str] = None
    consent_confirmation: Optional[str] = None
    
    # Dynamic Data
    custom_fields: Optional[dict] = None

@router.get("/lists", summary="List All Contact Lists")
async def list_contact_lists(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_view)
):
    query = db.query(ContactList)
    if not (current_user.role_obj.can_bypass_isolation if current_user.role_obj else current_user.role == "superadmin"):
        query = query.filter(ContactList.organization_id == current_user.organization_id)
        
    lists = query.order_by(ContactList.created_at.desc()).all()
    result = []
    for cl in lists:
        count = db.query(Contact).filter(Contact.list_id == cl.id).count()
        result.append({
            "id": str(cl.id),
            "name": cl.name,
            "description": cl.description,
            "count": count,
            "created_at": cl.created_at.isoformat() if cl.created_at else None,
        })
    return result


@router.post("/lists", summary="Create a Contact List")
async def create_contact_list(
    name: str = Body(...),
    description: str = Body(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    existing = db.query(ContactList).filter(
        ContactList.name == name,
        ContactList.organization_id == current_user.organization_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A list with this name already exists")
    new_list = ContactList(name=name, description=description, organization_id=current_user.organization_id)
    db.add(new_list)
    db.commit()
    db.refresh(new_list)
    return {"id": str(new_list.id), "name": new_list.name, "count": 0}


class ListFromSelectionRequest(BaseModel):
    name: str
    contact_ids: List[uuid.UUID]


@router.post("/lists/from-selection", summary="Create a Contact List from Selection")
async def create_list_from_selection(
    request: ListFromSelectionRequest,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    if not request.contact_ids:
        raise HTTPException(status_code=400, detail="No contacts selected")
    new_list = ContactList(
        name=request.name,
        description=f"Automated list from selection at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    db.add(new_list)
    db.commit()
    db.refresh(new_list)
    query = db.query(Contact).filter(Contact.id.in_(request.contact_ids))
    
    # Isolation: Verify ownership
    if not (current_user.role_obj.can_bypass_isolation if current_user.role_obj else current_user.role == "superadmin"):
        query = query.filter(Contact.organization_id == current_user.organization_id)
        
    updated_count = query.update(
        {"list_id": new_list.id}, synchronize_session=False
    )
    db.commit()
    return {"id": str(new_list.id), "name": new_list.name, "count": updated_count}


@router.get("/{contact_id}", summary="Get a Single Contact by ID")
def get_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_view)
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    # Isolation check
    verify_org_access(current_user, contact.organization_id)
        
    return contact

@router.patch("/{contact_id}", summary="Update a Single Contact")
async def update_contact(
    contact_id: uuid.UUID,
    contact_in: ContactUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(require_manage)
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    # Isolation check
    verify_org_access(current_user, contact.organization_id)

    update_data = contact_in.dict(exclude_unset=True)

    # Handle phone number update with validation
    if 'phone_number' in update_data and update_data['phone_number']:
        phone = update_data['phone_number']
        is_valid, cleaned, cc, err = validate_phone_number(phone)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid phone number: {err}")

        # Check for duplicates (excluding current contact)
        norm = normalize_phone(cleaned)
        existing = db.query(Contact).filter(
            or_(
                Contact.phone_number == cleaned,
                Contact.phone_number == norm,
                Contact.phone_number == f"+{norm}"
            ),
            Contact.id != contact_id  # Exclude current contact
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Another contact with this phone number already exists")

        # Update phone and country code
        update_data['phone_number'] = cleaned
        update_data['country_code'] = cc

    # Apply updates
    for field, value in update_data.items():
        if field == 'date_of_birth' and value:
            setattr(contact, field, parse_date(value))
        elif field == 'custom_fields' and value:
            # Merge custom fields instead of simple overwrite
            if not contact.custom_fields:
                contact.custom_fields = {}
            contact.custom_fields.update(value)
        else:
            setattr(contact, field, value)

    db.commit()
    db.refresh(contact)

    log_action(
        db, "UPDATE_CONTACT", "CONTACTS", 
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
        organization_id=current_user.organization_id,
        details={"phone": contact.phone_number, "name": contact.name},
        request=request
    )

    return contact

@router.delete("/{contact_id}", summary="Delete a Single Contact")
async def delete_contact(
    contact_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    # Isolation check
    verify_org_access(current_user, contact.organization_id)
    
    log_action(
        db, "DELETE_CONTACT", "CONTACTS", 
        user_id=str(current_user.id), impersonator_id=getattr(current_user, 'impersonator_id', None), username=current_user.username,
        details={"phone": contact.phone_number, "name": contact.name},
        request=request
    )

    db.delete(contact)
    db.commit()
    return {"message": "Contact deleted successfully"}
