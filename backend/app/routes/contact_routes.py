import csv
import io
import json
import uuid
import re
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from app.core.database import get_db
from app.models.contact import Contact, ContactList, ImportHistory, ContactStatus, ContactSource, ImportStatus
from app.core.security import get_current_user, RoleChecker
from app.models.agent import Agent

# Access control workers
admin_only = RoleChecker(["admin"])
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
    file: UploadFile = File(...),
    uploaded_by: Optional[str] = Form(None),
    list_id: Optional[uuid.UUID] = Form(None),
    field_mapping: Optional[str] = Form(None),
    upsert: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    filename = file.filename.lower()
    if not (filename.endswith('.csv') or filename.endswith('.xlsx')):
        raise HTTPException(400, "Only CSV and Excel (.xlsx) supported")
    
    file_type = 'csv' if filename.endswith('.csv') else 'xlsx'
    
    import_record = ImportHistory(
        filename=file.filename, file_type=file_type,
        uploaded_by=uploaded_by or "system", status=ImportStatus.PROCESSING.value
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
            
            if phone:
                is_valid, cleaned, _, _ = validate_phone_number(phone)
                if is_valid:
                    incoming_numbers.append(normalize_phone(cleaned))
        
        # Get existing normalized numbers that match our incoming batch (limit to 100 for SQL safety)
        existing_in_db_map = {}
        unique_incoming = list(set(incoming_numbers))
        if unique_incoming:
            # For large batches, we might need a more optimized query, 
            # but for stand-alone use cases, batch chunks of 100 is fine.
            existing_contacts = db.query(Contact).filter(
                or_(*[Contact.phone_number.like(f"%{num}") for num in unique_incoming[:100]])
            ).all()
            existing_in_db_map = {normalize_phone(c.phone_number): c for c in existing_contacts}

        success, duplicate, invalid, updated = 0, 0, 0, 0
        contacts_to_create = []
        seen_in_batch = set()
        
        for row in rows:
            # Resolve fields using mapping
            phone_col = mapping.get('phone_number')
            name_col = mapping.get('name')
            
            phone = row.get(phone_col) if phone_col else (row.get('phone_number') or row.get('phone') or row.get('mobile'))
            name = row.get(name_col) if name_col else (row.get('name') or row.get('full_name'))
            
            if not phone:
                invalid += 1; continue
            
            is_valid, cleaned, cc, err = validate_phone_number(phone)
            if not is_valid:
                invalid += 1; continue
                
            norm = normalize_phone(cleaned)
            
            if norm in seen_in_batch:
                duplicate += 1; continue
            seen_in_batch.add(norm)

            if norm in existing_in_db_map:
                if upsert:
                    existing_contact = existing_in_db_map[norm]
                    if name: existing_contact.name = name
                    if list_id: existing_contact.list_id = list_id
                    
                    # Update new fields on upsert using mapping where possible
                    def get_val(key, fallbacks):
                        col = mapping.get(key)
                        if col and col in row: return row[col]
                        for f in fallbacks:
                            if f in row: return row[f]
                        return None

                    existing_contact.company_name = get_val('company_name', ['company_name', 'company']) or existing_contact.company_name
                    existing_contact.lead_source = get_val('lead_source', ['lead_source', 'source']) or existing_contact.lead_source
                    dob_raw = get_val('date_of_birth', ['date_of_birth', 'dob'])
                    if dob_raw:
                        existing_contact.date_of_birth = parse_date(dob_raw)
                    existing_contact.customer_category = get_val('customer_category', ['customer_category', 'type']) or existing_contact.customer_category
                    existing_contact.customer_stage = get_val('customer_stage', ['customer_stage', 'stage']) or existing_contact.customer_stage
                    existing_contact.city = get_val('city', ['city']) or existing_contact.city
                    existing_contact.product_service_interest = get_val('product_service_interest', ['product_service_interest', 'interest']) or existing_contact.product_service_interest
                    existing_contact.consent_confirmation = get_val('consent_confirmation', ['consent_confirmation', 'consent']) or existing_contact.consent_confirmation
                    
                    updated += 1
                else:
                    duplicate += 1
                continue
            
            # Utility to get value from row based on mapping or fallbacks
            def get_row_val(key, fallbacks):
                col = mapping.get(key)
                if col and col in row: return row[col]
                for f in fallbacks:
                    if f in row: return row[f]
                return None

            contacts_to_create.append(Contact(
                phone_number=cleaned, 
                name=name, 
                country_code=cc,
                source=ContactSource.CSV.value, 
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
                consent_confirmation=get_row_val('consent_confirmation', ['consent_confirmation', 'consent'])
            ))
            success += 1
        
        if contacts_to_create:
            db.bulk_save_objects(contacts_to_create)
        
        db.commit()
        
        import_record.success_count = success
        import_record.duplicate_count = duplicate
        import_record.failed_count = invalid
        import_record.status = ImportStatus.COMPLETED.value
        import_record.completed_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": "Import completed", 
            "import_id": str(import_record.id), 
            "success": success, 
            "duplicates": duplicate, 
            "updated": updated,
            "invalid": invalid
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
    
    # New Fields
    company_name: Optional[str] = None
    lead_source: Optional[str] = None
    date_of_birth: Optional[str] = None # Will parse to datetime
    customer_category: Optional[str] = None
    customer_stage: Optional[str] = None
    city: Optional[str] = None
    product_service_interest: Optional[str] = None
    consent_confirmation: Optional[str] = None

@router.post("/", summary="Create Single Contact")
async def create_contact(
    contact: ContactCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    is_valid, cleaned, cc, err = validate_phone_number(contact.phone_number)
    if not is_valid:
        raise HTTPException(400, f"Invalid phone number: {err}")
    
    norm = normalize_phone(cleaned)
    # Strict duplicate check using normalized number
    query = db.query(Contact).filter(
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
            
            db.commit()
            db.refresh(existing)
            return existing
        else:
            raise HTTPException(400, "Contact with this phone number already exists")
    
    new_contact = Contact(
        phone_number=cleaned,
        name=contact.name,
        country_code=cc,
        source=ContactSource.MANUAL.value,
        list_id=contact.list_id,
        # New Fields
        company_name=contact.company_name,
        lead_source=contact.lead_source,
        date_of_birth=parse_date(contact.date_of_birth),
        customer_category=contact.customer_category,
        customer_stage=contact.customer_stage,
        city=contact.city,
        product_service_interest=contact.product_service_interest,
        consent_confirmation=contact.consent_confirmation
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact

@router.get("/", summary="List Contacts with Filters")
async def list_contacts(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    list_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    try:
        query = db.query(Contact)
        
        # 1. Search (Name/Phone)
        if search:
            query = query.filter(
                or_(
                    Contact.name.ilike(f"%{search}%"),
                    Contact.phone_number.ilike(f"%{search}%")
                )
            )
        
        # 2. Filters
        if status:
            query = query.filter(Contact.status == status)
        if list_id:
            query = query.filter(Contact.list_id == list_id)
        
        # 3. Total Count (before pagination)
        total = query.count()
        
        # 4. Paginate
        items = query.order_by(Contact.created_at.desc()).offset(offset).limit(limit).all()
        
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
    request: BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    query = db.query(Contact).filter(Contact.id.in_(request.contact_ids))
    
    if request.action == "delete":
        count = query.delete(synchronize_session=False)
        db.commit()
        return {"message": f"Successfully deleted {count} contacts"}
    
    elif request.action == "update_status":
        if not request.value:
            raise HTTPException(status_code=400, detail="Status value required")
        count = query.update({"status": request.value}, synchronize_session=False)
        db.commit()
        return {"message": f"Successfully updated status for {count} contacts"}
    
    elif request.action == "update_customer_category":
        if not request.value:
            raise HTTPException(status_code=400, detail="Category value required")
        count = query.update({"customer_category": request.value}, synchronize_session=False)
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

@router.get("/lists", summary="List All Contact Lists")
async def list_contact_lists(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    lists = db.query(ContactList).order_by(ContactList.created_at.desc()).all()
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
    current_user: Agent = Depends(any_agent)
):
    existing = db.query(ContactList).filter(ContactList.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="A list with this name already exists")
    new_list = ContactList(name=name, description=description)
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
    current_user: Agent = Depends(any_agent)
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
    db.query(Contact).filter(Contact.id.in_(request.contact_ids)).update(
        {"list_id": new_list.id}, synchronize_session=False
    )
    db.commit()
    return {"id": str(new_list.id), "name": new_list.name, "count": len(request.contact_ids)}


@router.get("/{contact_id}", summary="Get a Single Contact by ID")
def get_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact

@router.patch("/{contact_id}", summary="Update a Single Contact")

async def update_contact(
    contact_id: uuid.UUID,
    contact_in: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(any_agent)
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

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
        else:
            setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact

@router.delete("/{contact_id}", summary="Delete a Single Contact")
async def delete_contact(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(admin_only)
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    db.delete(contact)
    db.commit()
    return {"message": "Contact deleted successfully"}
