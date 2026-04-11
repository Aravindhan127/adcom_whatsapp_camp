import os
from pathlib import Path
from celery import Celery
from dotenv import load_dotenv

# Load .env relative to this file's location (works from any working directory)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# SECURITY: Use environment variable for Redis URL, fallback to default only in development
REDIS_URL = os.getenv("REDIS_URL") or "redis://127.0.0.1:6379/0"

celery_app = Celery(
    "adcom_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.campaign_worker"],
    set_as_current=True
)

celery_app.conf.update(
    task_always_eager=False, # Standard background processing
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1, # One task at a time per worker for rate control
    
    # Robustness for Startup/Windows
    broker_connection_retry_on_startup=True,
    task_track_started=True,
    task_default_queue="celery",
    task_create_missing_queues=True,
)

celery_app.conf.beat_schedule = {
    "check-scheduled-campaigns-every-minute": {
        "task": "check_scheduled_campaigns",
        "schedule": 60.0,
    },
}

if __name__ == "__main__":
    celery_app.start()
