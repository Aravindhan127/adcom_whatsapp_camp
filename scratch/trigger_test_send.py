import sys
import os
import uuid
import time

# Add backend to path to allow imports
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend"))

from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.contact import Contact
from app.routes.campaign_routes import start_campaign_run
from app.models.whatsapp_chat_model import WhatsAppMessage

db = SessionLocal()
try:
    print("--- DUPING AND TRIGGERING CAMPAIGN TEST ---")
    
    # 1. Fetch template campaign (testing14)
    old_camp = db.query(Campaign).filter(Campaign.name == "testing14").first()
    if not old_camp:
        print("ERROR: Campaign testing14 not found to duplicate!")
        sys.exit(1)
        
    print(f"Found old campaign: {old_camp.name} ({old_camp.id})")
    print(f"Params: {old_camp.template_params}")
    
    # 2. Create duplicated campaign
    new_name = f"testing15_{int(time.time())}"
    new_camp = Campaign(
        name=new_name,
        template_name=old_camp.template_name,
        contact_list_id=old_camp.contact_list_id,
        organization_id=old_camp.organization_id,
        status="draft",
        media_url=old_camp.media_url,
        template_params=old_camp.template_params,
        total_contacts=old_camp.total_contacts
    )
    db.add(new_camp)
    db.commit()
    db.refresh(new_camp)
    print(f"Created new campaign: {new_camp.name} ({new_camp.id})")
    
    # 3. Start campaign
    print(f"Triggering run for campaign: {new_camp.name}...")
    res = start_campaign_run(db, new_camp.id)
    print(f"Start Result: {res}")
    
    db.commit()
    
    # 4. Wait for Celery worker to process the campaign run
    print("Waiting 10 seconds for Celery worker to process...")
    for i in range(10):
        time.sleep(1)
        print(f"  {i+1}...")
        
    # 5. Fetch message logs
    print("\n--- NEW MESSAGE LOGS ---")
    msgs = db.query(WhatsAppMessage).filter(WhatsAppMessage.campaign_id == new_camp.id).all()
    if not msgs:
        print("No messages found for this campaign yet.")
    else:
        for m in msgs:
            print(f"Recipient: {m.wa_id}")
            print(f"Status: {m.delivery_status}")
            print(f"Error (if any): {m.status_error}")
            print(f"Meta Message ID: {m.meta_message_id}")
            print("-" * 30)

except Exception as e:
    print(f"ERROR: {str(e)}")
finally:
    db.close()
