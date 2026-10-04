"""
Celery application for OpsMind AI background workers.
Handles IMAP polling, SMTP dispatch, AI extraction, and other async tasks.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set default environment for Celery
os.environ.setdefault("ENVIRONMENT", "development")

# Celery app with Redis broker
celery_app = Celery(
    "opsmind",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=[
        "app.workers.tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_track_started=True,
    task_time_limit=300,  # 5 min hard limit
    task_soft_time_limit=240,  # 4 min soft limit
    # Worker configuration
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=100,
    # Result backend
    result_expires=3600,
    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat schedule (periodic tasks)
    beat_schedule={
        "poll-mailbox-every-30-seconds": {
            "task": "app.workers.tasks.poll_mailbox_task",
            "schedule": 30.0,  # Every 30 seconds
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.workers"])


@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing worker connectivity."""
    print(f"Request: {self.request!r}")