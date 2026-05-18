import uuid
from datetime import datetime
from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.contact import Contact, ContactList
from app.models.organization import OrganizationConfig
from app.services.campaign_service import start_campaign_run

def trigger():
    db = SessionLocal()
    try:
        # Get first org
        config = db.query(OrganizationConfig).first()
        org_id = config.organization_id if config else None
        
        # 1. Create a Contact List
        new_list = ContactList(
            name=f"Test Carousel {datetime.now().strftime('%H%M%S')}",
            organization_id=org_id,
            description="Fix verification"
        )
        db.add(new_list)
        db.commit()
        db.refresh(new_list)
        
        # 2. Add the contact
        contact = Contact(
            phone_number="917397349160",
            name="Aravindhan",
            list_id=new_list.id,
            organization_id=org_id
        )
        db.add(contact)
        db.commit()
        
        # 3. Create Campaign
        new_campaign = Campaign(
            name="Fix Test Carousel",
            template_name="carosuel_templete",
            contact_list_id=new_list.id,
            organization_id=org_id,
            status="draft",
            total_contacts=1
        )
        db.add(new_campaign)
        db.commit()
        db.refresh(new_campaign)
        
        print(f"Campaign created: {new_campaign.id}")
        
        # 4. Start Campaign
        print("Starting campaign...")
        res = start_campaign_run(db, new_campaign.id)
        print(f"Result: {res}")
        
    finally:
        db.close()

if __name__ == "__main__":
    trigger()
