import os
from pathlib import Path
from celery import Celery
from dotenv import load_dotenv

# Load .env relative to this file's location (works from any working directory)
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)

# SECURITY: Use environment variable for Redis URL (Remote instance)
REDIS_URL = os.getenv("REDIS_URL")

celery_app = Celery(
    "adcom_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    set_as_current=True
)

celery_app.conf.update(
    task_always_eager=False,      # Standard background processing
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1, # One task at a time per worker for rate control

    # Robustness for Startup/Windows/Python3.13
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_pool_limit=None,       # BE-FIX: Disable internal pooling to avoid 'NoneType' connection errors on Windows
    # BE-FIX: Socket keepalive settings for remote Redis stability on Windows
    broker_transport_options={
        'visibility_timeout': 36000, 
        'socket_keepalive': True,
        'socket_timeout': 30,
        'retry_on_timeout': True
    },
    task_track_started=True,
    task_default_queue="celery",
    task_create_missing_queues=True,
)

celery_app.conf.beat_schedule = {
    # BE-FIX: Trigger scheduled campaigns every 60 seconds
    "check-scheduled-campaigns-every-minute": {
        "task": "check_scheduled_campaigns",  # Must match @celery_app.task(name=...)
        "schedule": 10.0,
    },
    # BE-FIX BE-2: Resume on_hold campaigns every 30 minutes (was missing — campaigns stuck forever)
    "check-on-hold-campaigns-every-30-minutes": {
        "task": "check_on_hold_campaigns",    # Must match @celery_app.task(name=...)
        "schedule": 1800.0,                   # 30 minutes
    },
}

# BE-FIX: Register tasks and finalize app to bridge circular dependency correctly
celery_app.conf.update(include=['app.workers.campaign_worker'])
celery_app.finalize()

if __name__ == "__main__":
    celery_app.start()
