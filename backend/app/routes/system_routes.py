from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, PermissionChecker
from app.models.agent import Agent
from app.models.organization import Organization, OrganizationConfig
from app.models.settings import SystemSettings
from app.services.currency_service import update_system_exchange_rate
from pydantic import BaseModel
from typing import List, Optional
import uuid

# Only Super Admin can access these routes
super_admin_only = PermissionChecker("system.admin")

router = APIRouter(prefix="/system", tags=["System Administration"])

class OrgCreate(BaseModel):
    name: str
    slug: str

class ConfigUpdate(BaseModel):
    whatsapp_business_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    access_token: Optional[str] = None
    timezone: Optional[str] = None

@router.get("/organizations")
def list_organizations(
    db: Session = Depends(get_db),
    current_user: Agent = Depends(super_admin_only)
):
    orgs = db.query(Organization).all()
    result = []
    for org in orgs:
        config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == org.id).first()
        result.append({
            "id": org.id,
            "name": org.name,
            "slug": org.slug,
            "is_active": org.is_active,
            "created_at": org.created_at,
            "config": config
        })
    return result

@router.post("/organizations")
def create_organization(
    org_in: OrgCreate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(super_admin_only)
):
    existing = db.query(Organization).filter(Organization.slug == org_in.slug).first()
    if existing:
        raise HTTPException(status_code=400, detail="Organization slug already exists")
    
    new_org = Organization(name=org_in.name, slug=org_in.slug)
    db.add(new_org)
    db.flush()
    
    # Create empty config
    new_config = OrganizationConfig(organization_id=new_org.id)
    db.add(new_config)
    db.commit()
    db.refresh(new_org)
    return new_org

@router.patch("/organizations/{org_id}/config")
def update_org_config(
    org_id: uuid.UUID,
    config_in: ConfigUpdate,
    db: Session = Depends(get_db),
    current_user: Agent = Depends(super_admin_only)
):
    config = db.query(OrganizationConfig).filter(OrganizationConfig.organization_id == org_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found for this organization")
    
    if config_in.whatsapp_business_id is not None:
        config.whatsapp_business_id = config_in.whatsapp_business_id
    if config_in.phone_number_id is not None:
        config.phone_number_id = config_in.phone_number_id
    if config_in.access_token is not None:
        config.access_token = config_in.access_token
    if config_in.timezone is not None:
        config.timezone = config_in.timezone
        
    db.commit()
    return {"message": "Configuration updated successfully"}

@router.get("/dashboard-stats")
def get_system_stats(
    org_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: Agent = Depends(super_admin_only)
):
    """Global stats across all organizations."""
    from app.models.campaign import Campaign
    from app.models.contact import Contact
    from app.models.whatsapp_conversation import WhatsAppConversation
    query_orgs = db.query(Organization)
    query_agents = db.query(Agent)
    query_campaigns = db.query(Campaign)
    query_contacts = db.query(Contact)
    
    if org_id:
        query_agents = query_agents.filter(Agent.organization_id == org_id)
        query_campaigns = query_campaigns.filter(Campaign.organization_id == org_id)
        query_contacts = query_contacts.filter(Contact.organization_id == org_id)
        # We don't filter Organizations count as it's a global stat, but we could return specific org info
    
    total_orgs = query_orgs.count()
    total_agents = query_agents.count()
    total_campaigns = query_campaigns.count()
    total_contacts = query_contacts.count()
    
    return {
        "organizations": total_orgs,
        "agents": total_agents,
        "campaigns": total_campaigns,
        "contacts": total_contacts,
        "active_orgs": query_orgs.filter(Organization.is_active == True).count()
    }

@router.get("/currency")
def get_exchange_rate(db: Session = Depends(get_db), current_user: Agent = Depends(get_current_user)):
    """Retrieve current exchange rate (Agents + Admins)."""
    settings = SystemSettings.get_settings(db)
    return {
        "exchange_rate": settings.exchange_rate,
        "last_updated": settings.updated_at
    }

@router.post("/currency/sync")
def sync_exchange_rate(db: Session = Depends(get_db), current_user: Agent = Depends(super_admin_only)):
    """Manually sync live exchange rate (Super Admin only)."""
    rate = update_system_exchange_rate(db)
    if not rate:
        raise HTTPException(status_code=500, detail="Failed to sync live rate")
    return {"message": "Exchange rate synced successfully", "rate": rate}
