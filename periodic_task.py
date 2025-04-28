from celery.schedules import crontab
from celery_config import celery_app

celery_app.conf.timezone = 'Europe/Athens'  # Greek time
celery_app.conf.enable_utc = False  # Ensure it doesn't use UTC
