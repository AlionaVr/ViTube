from app.core.config import get_settings
from celery import Celery

# Redis is the broker. Video tasks are added in Stage 3.
celery_app = Celery("vitube", broker=str(get_settings().redis_url))
celery_app.conf.broker_connection_retry_on_startup = True
