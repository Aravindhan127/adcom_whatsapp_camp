import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun

def cleanup():
    db = SessionLocal()
    try:
        # Find all paused campaigns
        paused_campaigns = db.query(Campaign).filter(Campaign.status == "paused").all()
        print(f"Found {len(paused_campaigns)} paused campaigns.")
        
        for c in paused_campaigns:
            # Check most recent run
            last_run = db.query(CampaignRun).filter(CampaignRun.campaign_id == c.id).order_by(CampaignRun.started_at.desc()).first()
            if not last_run:
                continue
                
            # If processed equals or exceeds total, it should be marked as completed
            if last_run.processed_count >= c.total_contacts and c.total_contacts > 0:
                print(f"Repairing Campaign: {c.name} ({c.id}) -> Set to Completed")
                c.status = "completed"
                last_run.status = "completed"
        
        db.commit()
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup()
