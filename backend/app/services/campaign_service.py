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
import logging

logger = logging.getLogger("adcom-api")

BATCH_SIZE = 1000

def _check_redis_ready() -> Optional[str]:
    """
    Pre-flight check: verify Redis is reachable before attempting to queue tasks.
    Returns an error string if Redis is down, or None if OK.
    """
    try:
        r = redis_lib.from_url(REDIS_URL, socket_connect_timeout=3)
        r.ping()
        logger.debug("CampaignService: Redis pre-flight check passed.")
        return None
    except Exception as e:
        msg = (
            f"Messaging Engine (Redis) is not reachable at {REDIS_URL}. "
            f"Please ensure Redis and the Celery worker are running. "
            f"Run: .\\start.ps1 to start all services. Error: {str(e)}"
        )
        logger.error(f"CampaignService: Redis pre-flight FAILED: {str(e)}")
        return msg


def start_campaign_run(db: Session, campaign_id: uuid.UUID, scheduled_at: Optional[datetime] = None):
    logger.info(f"CampaignService: start_campaign_run called for campaign={campaign_id}, scheduled_at={scheduled_at}")

    # Pre-flight: verify Redis/Celery is reachable BEFORE doing any DB work
    redis_error = _check_redis_ready()
    if redis_error:
        return {"error": redis_error}

    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        logger.error(f"CampaignService: Campaign {campaign_id} not found in DB")
        return {"error": "Campaign not found"}

    # Check if campaign is resuming from on_hold - reuse existing run
    if campaign.status == "on_hold":
        logger.info(f"CampaignService: Resuming on_hold campaign {campaign.name}")
        existing_run = db.query(CampaignRun).filter(
            CampaignRun.campaign_id == campaign_id,
            CampaignRun.status == "on_hold"
        ).first()
        if existing_run:
            existing_run.status = "running"
            existing_run.on_hold_since = None
            campaign.status = "running"
            db.commit()
            logger.info(f"CampaignService: Resumed run {existing_run.id} from offset {existing_run.last_processed_offset}")
            from app.workers.campaign_worker import send_campaign_batch
            next_offset = existing_run.last_processed_offset or existing_run.processed_count
            task = send_campaign_batch.delay(
                str(existing_run.id),
                str(campaign_id),
                next_offset,
                BATCH_SIZE
            )
            return {"message": "Campaign resumed", "run_id": str(existing_run.id), "task_id": str(task.id)}

    # Check Meta Daily Limits
    if not is_within_limits(db):
        logger.warning(f"CampaignService: Meta Daily Limit Reached for campaign {campaign_id}")
        return {"error": "Meta Daily Limit Reached (Tier 1: 1k/day). Please wait 24h to avoid a ban."}

    # Check template exists and is APPROVED
    logger.info(f"CampaignService: Checking template '{campaign.template_name}'")
    template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == campaign.template_name).first()
    if not template:
        logger.error(f"CampaignService: Template '{campaign.template_name}' not found in local DB")
        return {"error": f"Template '{campaign.template_name}' not found"}
    if template.status != "APPROVED":
        logger.error(f"CampaignService: Template '{campaign.template_name}' status is '{template.status}' — not APPROVED")
        return {"error": f"Template '{campaign.template_name}' is not approved by Meta (status: {template.status})"}

    # Count contacts
    logger.info(f"CampaignService: Counting contacts for list {campaign.contact_list_id}")
    total_contacts = db.query(Contact).filter(Contact.list_id == campaign.contact_list_id).count()
    if total_contacts == 0:
        logger.error(f"CampaignService: No contacts found in list {campaign.contact_list_id}")
        return {"error": "No contacts in the list"}

    campaign.total_contacts = total_contacts
    logger.info(f"CampaignService: Total contacts = {total_contacts}")

    # BE-FIX BE-4: If campaign was in 'scheduled' state and user manually starts it,
    # force scheduled_at=None so we go to immediate launch (v2), not re-schedule.
    effective_scheduled_at = scheduled_at
    if campaign.status == "scheduled":
        logger.info(f"CampaignService: Campaign was 'scheduled', forcing immediate launch (ignoring scheduled_at).")
        effective_scheduled_at = None

    # BE-FIX FE-Scheduling: If scheduled_at is provided but is in the past,
    # treat it as an immediate launch to avoid 1-minute delay before Beat sees it.
    if effective_scheduled_at and effective_scheduled_at <= datetime.now(timezone.utc):
        logger.info(f"CampaignService: scheduled_at ({effective_scheduled_at}) is in the past. Launching immediately.")
        effective_scheduled_at = None

    # Case 1: Start Immediately
    if not effective_scheduled_at:
        logger.info(f"CampaignService: Starting immediately via V2...")
        return start_campaign_run_v2(db, campaign_id)

    # Case 2: Schedule for Future
    logger.info(f"CampaignService: Scheduling for: {scheduled_at}")
    campaign.scheduled_at = scheduled_at
    campaign.status = "scheduled"
    db.commit()
    return {"message": "Campaign scheduled", "scheduled_at": str(scheduled_at)}


def start_campaign_run_v2(db: Session, campaign_id: uuid.UUID):
    """
    Direct immediate launch of a campaign run.
    Called from: (a) start_campaign_run when no schedule, (b) Celery Beat check_scheduled_campaigns.
    BE-FIX BE-5: Template validations added (was missing for Beat path).
    BE-FIX BE-6: Redis check added (was missing for Beat path).
    BE-FIX BE-3: No longer double-counts contacts — only counts if not already set.
    """
    logger.info(f"CampaignService V2: Initializing run for campaign={campaign_id}")
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        logger.error(f"CampaignService V2: Campaign {campaign_id} not found")
        return {"error": "Campaign not found during V2 launch"}

    # BE-FIX BE-6: Redis check (critical for Beat path — without this, run is created but task never queues)
    redis_error = _check_redis_ready()
    if redis_error:
        logger.error(f"CampaignService V2: Redis not ready — aborting to prevent zombie run: {redis_error}")
        return {"error": redis_error}

    # BE-FIX BE-5: Template check (critical for Beat path — was not done before)
    logger.info(f"CampaignService V2: Checking template '{campaign.template_name}'")
    template = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.name == campaign.template_name).first()
    if not template:
        logger.error(f"CampaignService V2: Template '{campaign.template_name}' not found — aborting scheduled launch")
        return {"error": f"Template '{campaign.template_name}' not found"}
    if template.status != "APPROVED":
        logger.error(f"CampaignService V2: Template '{campaign.template_name}' is '{template.status}' — aborting")
        return {"error": f"Template '{campaign.template_name}' is not approved (status: {template.status})"}

    # BE-FIX BE-3: Always re-count fresh for scheduled campaigns (total_contacts may be 0 at schedule time)
    total_contacts = db.query(Contact).filter(Contact.list_id == campaign.contact_list_id).count()
    if total_contacts == 0:
        logger.error(f"CampaignService V2: No contacts in list {campaign.contact_list_id}")
        return {"error": "No contacts in the list"}
    campaign.total_contacts = total_contacts
    logger.info(f"CampaignService V2: Total contacts = {total_contacts}")

    # Create Run record
    new_run = CampaignRun(
        campaign_id=campaign_id,
        status="running",
        total_contacts=total_contacts,
        started_at=datetime.now(timezone.utc)
    )
    db.add(new_run)
    campaign.status = "running"

    try:
        db.commit()
        db.refresh(new_run)
        logger.info(f"CampaignService V2: DB committed. Run ID={new_run.id}")
    except Exception as dbe:
        db.rollback()
        logger.error(f"CampaignService V2: DB commit failed: {str(dbe)}")
        return {"error": f"Database commit failed: {str(dbe)}"}

    # Queue first batch
    logger.info(f"CampaignService V2: Queuing first batch task...")
    from app.workers.campaign_worker import send_campaign_batch
    try:
        task = send_campaign_batch.delay(
            str(new_run.id),
            str(campaign_id),
            0,
            BATCH_SIZE
        )
        logger.info(f"CampaignService V2: Task queued. Task ID={task.id}")
        return {"message": "Campaign started", "run_id": str(new_run.id), "task_id": str(task.id)}
    except Exception as te:
        import traceback
        full_stack = traceback.format_exc()
        error_msg = f"Messaging Engine Error: Redis/Celery task queueing failed. ({str(te)})"
        logger.critical(f"CampaignService V2: Task queue FAILED for campaign {campaign_id}. Stack: {full_stack}")
        try:
            campaign.status = "draft"
            db.delete(new_run)
            db.commit()
        except Exception:
            pass
        return {"error": error_msg}


def pause_campaign(db: Session, campaign_id: uuid.UUID):
    logger.info(f"CampaignService: pause_campaign called for {campaign_id}")
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        return {"error": "Campaign not found"}
    if campaign.status != "running":
        return {"error": f"Cannot pause campaign in state '{campaign.status}'"}

    campaign.status = "paused"
    run = db.query(CampaignRun).filter(
        CampaignRun.campaign_id == campaign_id,
        CampaignRun.status == "running"
    ).first()
    if run:
        run.status = "paused"
        logger.info(f"CampaignService: Run {run.id} paused at offset {run.last_processed_offset}")

    db.commit()
    return {"message": "Campaign paused successfully. Current batch will complete soon."}


def resume_campaign(db: Session, campaign_id: uuid.UUID):
    logger.info(f"CampaignService: resume_campaign called for {campaign_id}")
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        return {"error": "Campaign not found"}
    if campaign.status != "paused":
        return {"error": f"Cannot resume campaign from state '{campaign.status}'"}

    redis_error = _check_redis_ready()
    if redis_error:
        return {"error": redis_error}

    campaign.status = "running"
    run = db.query(CampaignRun).filter(
        CampaignRun.campaign_id == campaign_id,
        CampaignRun.status == "paused"
    ).first()
    if not run:
        return {"error": "No paused run found to resume"}

    run.status = "running"
    db.commit()

    from app.workers.campaign_worker import send_campaign_batch
    next_offset = run.last_processed_offset or 0
    logger.info(f"CampaignService: Resuming run {run.id} from offset {next_offset}")
    task = send_campaign_batch.delay(
        str(run.id),
        str(campaign_id),
        next_offset,
        BATCH_SIZE
    )
    return {"message": "Campaign resumed", "run_id": str(run.id), "task_id": str(task.id)}
