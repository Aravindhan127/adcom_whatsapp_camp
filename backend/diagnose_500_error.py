import uuid
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.campaign_service import start_campaign_run_v2

# ID from user's request
campaign_id_str = "48614ee0-d1b4-42d3-8f1c-b32aba2fb60b"
campaign_id = uuid.UUID(campaign_id_str)

db = SessionLocal()
try:
    print(f"Executing diagnostic for campaign {campaign_id}...")
    result = start_campaign_run_v2(db, campaign_id)
    print("Result:", result)
except Exception as e:
    import traceback
    print("CRITICAL ERROR DURING DIAGNOSTIC:")
    print(traceback.format_exc())
finally:
    db.close()
