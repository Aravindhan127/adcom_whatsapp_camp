import uuid
from app.core.database import SessionLocal, Base, engine
from app.models.organization import Organization, OrganizationConfig
from app.models.agent import Agent
from app.models.campaign import Campaign
from app.models.contact import Contact, ContactList, ImportHistory
from app.models.template import WhatsAppTemplate
from app.models.whatsapp_conversation import WhatsAppConversation
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")

def migrate():
    db = SessionLocal()
    try:
        # 1. Create Default Organization
        default_org = db.query(Organization).filter(Organization.slug == "default").first()
        if not default_org:
            logger.info("Creating default organization...")
            default_org = Organization(
                name="Default Organization",
                slug="default",
                is_active=True
            )
            db.add(default_org)
            db.flush() # Get ID
            
            # 2. Create Org Config using current global settings
            config = OrganizationConfig(
                organization_id=default_org.id,
                whatsapp_business_id=settings.WABA_ID,
                phone_number_id=settings.PHONE_NUMBER_ID,
                access_token=settings.WHATSAPP_TOKEN,
                waba_status="approved"
            )
            db.add(config)
            logger.info(f"Created Org Config for {default_org.name}")
        else:
            logger.info("Default organization already exists.")

        # 3. Assign all existing data to default org
        org_id = default_org.id
        
        models_to_update = [
            Agent, Campaign, Contact, ContactList, 
            ImportHistory, WhatsAppTemplate, WhatsAppConversation
        ]
        
        for model in models_to_update:
            count = db.query(model).filter(model.organization_id == None).update(
                {model.organization_id: org_id}, synchronize_session=False
            )
            logger.info(f"Updated {count} records in {model.__tablename__}")
            
        db.commit()
        logger.info("Migration to multi-tenant completed successfully.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Migration failed: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    migrate()
