
from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun
from app.models.whatsapp_chat_model import WhatsAppMessage

db = SessionLocal()
try:
    print("--- LAST 5 CAMPAIGNS ---")
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).limit(5).all()
    for c in campaigns:
        print(f"ID: {c.id} | Name: {c.name} | Status: {c.status} | Template: {c.template_name}")
        if c.failure_reason:
            print(f"  Failure Reason: {c.failure_reason}")
    
    print("\n--- LAST 5 RUNS ---")
    runs = db.query(CampaignRun).order_by(CampaignRun.started_at.desc()).limit(5).all()
    for r in runs:
        print(f"ID: {r.id} | Campaign ID: {r.campaign_id} | Status: {r.status}")
        if r.failure_reason:
            print(f"  Failure Reason: {r.failure_reason}")

    print("\n--- LAST 5 MESSAGES ---")
    messages = db.query(WhatsAppMessage).order_by(WhatsAppMessage.created_at.desc()).limit(5).all()
    for m in messages:
        print(f"ID: {m.id} | To: {m.wa_id} | Status: {m.delivery_status}")
        if m.status_error:
            print(f"  Error: {m.status_error}")

finally:
    db.close()
