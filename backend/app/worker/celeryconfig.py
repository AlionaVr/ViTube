"""Celery settings. Celery imports this module on first use of its config."""

from app.core.config import get_settings
from app.modules.videos.pipeline import PROCESSING_LEASE

broker_url = str(get_settings().redis_url)  # Redis is the broker
broker_connection_retry_on_startup = True
include = ["app.modules.videos.tasks"]

task_ignore_result = True  # no result backend: outcomes live in the videos table
task_acks_late = True  # a worker that dies mid-job leaves the message for a restart
worker_prefetch_multiplier = 1  # jobs take minutes: don't hold messages another worker could take
# Longer than any job, or Redis hands a running job to another worker.
broker_transport_options = {"visibility_timeout": int(PROCESSING_LEASE.total_seconds()) + 3600}

beat_schedule = {
    "requeue-stuck-videos": {"task": "videos.requeue", "schedule": 60.0},
}
