from typing import Optional
import uuid
import redis as redis_lib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.campaign import Campaign
from app.models.campaign_run import CampaignRun
from app.models.contact import Contact
from app.models.template import WhatsAppTemplate
from app.services.restriction_service import is_within_limits
from app.core.celery_app import REDIS_URL

BATCH_SIZE = 1000

def _check_redis_ready() -> Optional[str]:
    """
    Pre-flight check: verify Redis is reachable before attempting to queue tasks.
    Returns an error string if Redis is down, or None if OK.
    """
    try:
        r = redis_lib.from_url(REDIS_URL, socket_connect_timeout=3)
        r.ping()
        return None
    except Exception as e:
        return (
            f"Messaging Engine (Redis) is not reachable at {REDIS_URL}. "
            f"Please ensure Redis and the Celery worker are running. "
            f"Run: .\\start.ps1 to start all services. Error: {str(e)}"
        )


def start_campaign_run(db: Session, campaign_id: uuid.UUID, scheduled_at: Optional[datetime] = None):
    print(f"Service: Starting campaign run for ID: {campaign_id}")

    # Pre-flight: verify Redis/Celery is reachable BEFORE doing any DB work
    redis_error = _check_redis_ready()
    if redis_error:
        print(f"Service CRITICAL: {redis_error}")
        return {"error": redis_error}

    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        print(f"Service Error: Campaign {campaign_id} not found in DB")
        return {"error": "Campaign not found"}

    # Check if campaign is resuming from on_hold - reuse existing run
    if campaign.status == "on_hold":
        print(f"Service: Resuming on_hold campaign...")
        existing_run = db.query(CampaignRun).filter(
            CampaignRun.campaign_id == campaign_id,
            CampaignRun.status == "on_hold"
        ).first()
        if existing_run:
            # Reset status and resume from last position
            existing_run.status = "running"
            existing_run.on_hold_since = None
            campaign.status = "running"
            db.commit()
            print(f"Service: Resumed existing run {existing_run.id} from offset {existing_run.last_processed_offset}")
            # Trigger next batch from last position
            from app.workers.campaign_worker import send_campaign_batch
            next_offset = existing_run.last_processed_offset or existing_run.processed_count
            task = send_campaign_batch.delay(
                str(existing_run.id),
                str(campaign_id),
                next_offset,
                BATCH_SIZE
            )
            return {"message": "Campaign resumed", "run_id": str(existing_run.id), "task_id": str(task.id)}

    # Check Meta Daily Limits (Rule 10)
    print(f"Service: Checking daily limits...")
    if not is_within_limits(db):
        print(f"Service Error: Meta Daily Limit Reached")
        return {"error": "Meta Daily Limit Reached (Tier 1: 1k/day). Please wait 24h to avoid a ban."}

    # Check template
    print(f"Service: Checking template: {campaign.template_name}")
    template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == campaign.template_name).first()
    if not template:
        print(f"Service Error: Template '{campaign.template_name}' not found")
        return {"error": f"Template '{campaign.template_name}' not found"}

    if template.status != "APPROVED":
        print(f"Service Error: Template '{campaign.template_name}' is of status {template.status}")
        return {"error": "Template not approved by Meta"}

    # Count contacts
    print(f"Service: Counting contacts for list: {campaign.contact_list_id}")
    total_contacts = db.query(Contact).filter(Contact.list_id == campaign.contact_list_id).count()
    if total_contacts == 0:
        print(f"Service Error: No contacts found in list {campaign.contact_list_id}")
        return {"error": "No contacts in the list"}

    # Update Total Count for tracking
    campaign.total_contacts = total_contacts
    print(f"Service: Total contacts to process: {total_contacts}")

    # Case 1: Start Immediately
    if not scheduled_at:
        print(f"Service: Starting immediately via V2...")
        return start_campaign_run_v2(db, campaign_id)

    # Case 2: Schedule for Future
    print(f"Service: Scheduling for: {scheduled_at}")
    campaign.scheduled_at = scheduled_at
    campaign.status = "scheduled"
    db.commit()
    return {"message": "Campaign scheduled", "scheduled_at": str(scheduled_at)}

def start_campaign_run_v2(db: Session, campaign_id: uuid.UUID):
    print(f"Service V2: Initializing run for campaign: {campaign_id}")
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        return {"error": "Campaign not found during V2 launch"}
    
    # Create Run record
    new_run = CampaignRun(
        campaign_id=campaign_id,
        status="running",
        total_contacts=campaign.total_contacts,
        started_at=datetime.now(timezone.utc)
    )
    db.add(new_run)
    campaign.status = "running"
    
    try:
        db.commit()
        db.refresh(new_run)
        print(f"Service V2: DB Committed. Run ID: {new_run.id}")
    except Exception as dbe:
        db.rollback()
        return {"error": f"Database commit failed: {str(dbe)}"}

    # Queue only the first batch (The worker will chain the next one)
    print(f"Service V2: Importing campaign_worker...")
    from app.workers.campaign_worker import send_campaign_batch
    
    print(f"Service V2: Delaying Celery task 'send_campaign_batch'...")
    try:
        # Reverting to .delay() for proper asynchronous execution (background sending)
        # Pre-flight: This will throw an OperationalError if Redis is down
        task = send_campaign_batch.delay(
            str(new_run.id),
            str(campaign_id),
            0,
            BATCH_SIZE
        )
        print(f"Service V2: Task queued successfully. Task ID: {task.id}")
        return {"message": "Campaign started", "run_id": str(new_run.id), "task_id": str(task.id)}
    except Exception as te:
        error_msg = f"Messaging Engine Error: Redis connection refused. Please ensure Redis-server is running. ({str(te)})"
        print(f"Service V2 CRITICAL ERROR: {error_msg}")
        
        # Rollback the status to 'draft' or 'on_hold' so it can be re-tried
        try:
            campaign.status = "draft"
            db.delete(new_run)
            db.commit()
        except: pass
        
        return {"error": error_msg}

def pause_campaign(db: Session, campaign_id: uuid.UUID):
    print(f"Service: Pausing campaign {campaign_id}")
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        return {"error": "Campaign not found"}
    
    if campaign.status != "running":
        return {"error": f"Cannot pause campaign in state '{campaign.status}'"}
    
    # Update Campaign status
    campaign.status = "paused"
    
    # Update current Run status
    run = db.query(CampaignRun).filter(
        CampaignRun.campaign_id == campaign_id,
        CampaignRun.status == "running"
    ).first()
    if run:
        run.status = "paused"
    
    db.commit()
    return {"message": "Campaign paused successfully. Final batch will complete soon."}

def resume_campaign(db: Session, campaign_id: uuid.UUID):
    print(f"Service: Resuming campaign {campaign_id}")
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        return {"error": "Campaign not found"}
    
    if campaign.status != "paused":
        return {"error": f"Cannot resume campaign from state '{campaign.status}'"}
    
    # Verify Redis first
    redis_error = _check_redis_ready()
    if redis_error:
        return {"error": redis_error}

    campaign.status = "running"
    
    # Find the last paused run
    run = db.query(CampaignRun).filter(
        CampaignRun.campaign_id == campaign_id,
        CampaignRun.status == "paused"
    ).first()
    
    if not run:
        return {"error": "No paused run found to resume"}
        
    run.status = "running"
    db.commit()
    
    # Trigger the next batch
    from app.workers.campaign_worker import send_campaign_batch
    next_offset = run.last_processed_offset or 0
    task = send_campaign_batch.delay(
        str(run.id),
        str(campaign_id),
        next_offset,
        BATCH_SIZE
    )
    
    return {"message": "Campaign resumed", "run_id": str(run.id), "task_id": str(task.id)}
