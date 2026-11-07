"""Celery settings. Celery imports this module on first use of its config."""

from app.core.config import get_settings

broker_url = str(get_settings().redis_url)  # Redis is the broker
broker_connection_retry_on_startup = True
