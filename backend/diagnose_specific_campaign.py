import sys
import os
import uuid
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add current dir to sys.path to import app
sys.path.append(os.getcwd())

from app.core.config import settings
from app.models.campaign import Campaign
from app.models.contact import ContactList, Contact
from app.models.template import WhatsAppTemplate

print(f"DEBUG: DATABASE_URL is {settings.DATABASE_URL}")

engine = create_engine(settings.DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def full_diagnostic():
    target_id = "309598e7-e58c-45e8-84b0-6ad393669a00"
    print(f"\n--- DIAGNOSING CAMPAIGN {target_id} ---")
    
    try:
        # 1. Fetch Campaign
        campaign = session.query(Campaign).filter(Campaign.id == target_id).first()
        if not campaign:
            print(f"ERROR: Campaign {target_id} not found.")
            # Check if it's a contact list ID by mistake
            clist = session.query(ContactList).filter(ContactList.id == target_id).first()
            if clist:
                print(f"INFO: ID {target_id} is a ContactList, not a Campaign.")
            return

        print(f"SUCCESS: Found Campaign '{campaign.name}'")
        print(f"Status: {campaign.status}")
        print(f"Template Name: {campaign.template_name}")
        print(f"Contact List ID: {campaign.contact_list_id}")

        # 2. Check Template
        template = session.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == campaign.template_name).first()
        if not template:
            print(f"ERROR: Template '{campaign.template_name}' not found in database.")
        else:
            print(f"SUCCESS: Template '{template.name}' found. Status: {template.status}")

        # 3. Check Contacts
        contact_count = session.query(Contact).filter(Contact.list_id == campaign.contact_list_id).count()
        print(f"INFO: Contacts in list: {contact_count}")
        if contact_count == 0:
            print("ERROR: No contacts found in the associated list.")

        # 4. Check if CampaignRun already exists
        from app.models.campaign_run import CampaignRun
        run = session.query(CampaignRun).filter(CampaignRun.campaign_id == target_id).first()
        if run:
            print(f"INFO: CampaignRun already exists for this campaign. ID={run.id}, Status={run.status}")
        else:
            print("INFO: No CampaignRun found yet.")

    except Exception as e:
        print(f"EXCEPTION during diagnosis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    full_diagnostic()
