from celery import Celery

# Settings are read on first use (celeryconfig), so importing this module never needs env vars.
celery_app = Celery("vitube")
celery_app.config_from_object("app.worker.celeryconfig")
