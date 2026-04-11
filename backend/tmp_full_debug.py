
import os
import sys
import uuid
import requests

# Set the working directory to backend
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.contact import Contact, ContactList
from app.services.campaign_service import start_campaign_run

def debug_full_flow():
    db = SessionLocal()
    campaign_id = 'dc1d14cb-9c27-4208-82ee-babc4ce11205'
    
    print(f"--- Debugging Campaign {campaign_id} ---")
    
    try:
        # 1. Ensure Campaign and Contacts exist
        c = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not c:
            print("Campaign not found. Creating...")
            # Get or create a list
            clist = db.query(ContactList).first()
            if not clist:
                clist = ContactList(name="Test List")
                db.add(clist)
                db.commit()
                db.refresh(clist)
            
            c = Campaign(
                id=uuid.UUID(campaign_id),
                name="Debug Full Flow",
                template_name="hello_world",
                contact_list_id=clist.id,
                status="draft"
            )
            db.add(c)
            db.commit()
            db.refresh(c)
        
        # 2. Reset Status
        c.status = "draft"
        db.commit()
        print(f"Status reset to: {c.status}")
        
        # 3. Ensure contacts are in the list
        count = db.query(Contact).filter(Contact.list_id == c.contact_list_id).count()
        print(f"Contacts in list: {count}")
        if count == 0:
            print("Adding dummy contacts...")
            db.add(Contact(name="Test 1", phone_number="918000000001", list_id=c.contact_list_id))
            db.add(Contact(name="Test 2", phone_number="917397349160", list_id=c.contact_list_id))
            db.commit()
            print("Contacts added.")

        # 4. Trigger via API (Testing the route)
        print("Calling API POST /campaigns/{id}/start...")
        try:
            r = requests.post(f"http://127.0.0.1:8000/campaigns/{campaign_id}/start", timeout=30)
            print(f"API Response Status: {r.status_code}")
            print(f"API Response Body: {r.text}")
        except Exception as api_err:
            print(f"API Call failed: {api_err}")
            print("Falling back to direct service call for debugging...")
            res = start_campaign_run(db, uuid.UUID(campaign_id))
            print(f"Service result: {res}")

        # 5. Final Check
        db.refresh(c)
        print(f"Final Campaign Status: {c.status}")
        print(f"Sent Count: {c.sent_count}, Failed Count: {c.failed_count}")

    except Exception as e:
        print(f"CRITICAL ERROR in debug script: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    debug_full_flow()
