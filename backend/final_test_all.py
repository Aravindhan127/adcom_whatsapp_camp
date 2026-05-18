import time
import uuid
from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun
from app.models.contact import Contact
from app.workers.campaign_worker import send_campaign_batch

def trigger_test(template_name):
    db = SessionLocal()
    try:
        # 1. Find or create a test campaign for this template
        campaign = db.query(Campaign).filter(Campaign.template_name == template_name).first()
        if not campaign:
            print(f"No campaign found for {template_name}")
            return

        # 2. Find a contact
        contact = db.query(Contact).first()
        if not contact:
            print("No contacts found")
            return

        # 3. Create a new Run
        run_id = str(uuid.uuid4())
        run = CampaignRun(
            id=run_id,
            campaign_id=campaign.id,
            total_contacts=1,
            status="running"
        )
        db.add(run)
        db.commit()

        print(f"Triggering {template_name} for {contact.phone_number} (Run: {run_id})")
        # Trigger worker
        send_campaign_batch.delay(run_id, str(campaign.id), 0, 1)
        
    finally:
        db.close()

if __name__ == "__main__":
    templates = ["hello_world", "video_template", "carosuel_templete"]
    for t in templates:
        trigger_test(t)
        time.sleep(2)
