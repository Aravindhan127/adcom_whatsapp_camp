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
from app.models.contact import ContactList

print(f"DEBUG: DATABASE_URL is {settings.DATABASE_URL}")

engine = create_engine(settings.DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

def full_diagnostic():
    print("\n--- DATABASE DIAGNOSTIC ---")
    
    # 1. Check if tables exist
    try:
        res = session.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';"))
        tables = [r[0] for r in res]
        print(f"Tables found: {tables}")
    except Exception as e:
        print(f"Error listing tables: {e}")

    # 2. Total campaign count
    try:
        campaign_count = session.query(Campaign).count()
        print(f"Total Campaigns: {campaign_count}")
        
        if campaign_count > 0:
            all_campaigns = session.query(Campaign).all()
            for c in all_campaigns:
                print(f"Campaign: ID={c.id}, Name={c.name}, Status={c.status}, ListID={c.contact_list_id}")
    except Exception as e:
        print(f"Error querying campaigns: {e}")

    # 3. Target campaign check
    target_id = "dc1d14cb-9c27-4208-82ee-babc4ce11205"
    try:
        target = session.query(Campaign).filter(Campaign.id == target_id).first()
        if target:
            print(f"SUCCESS: Found target campaign {target_id}")
            print(f"Status: {target.status}, Template: {target.template_name}")
        else:
            print(f"FAILURE: Target campaign {target_id} NOT found in campaigns table.")
            
            # Check other tables for this UUID just in case (ContactList, etc)
            clist = session.query(ContactList).filter(ContactList.id == target_id).first()
            if clist:
                print(f"INFO: The ID {target_id} actually belongs to a CONTACT LIST, not a campaign.")
    except Exception as e:
        print(f"Error checking target ID: {e}")

    session.close()

if __name__ == "__main__":
    full_diagnostic()
