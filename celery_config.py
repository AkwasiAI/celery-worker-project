# celery_config.py
import os
from celery import Celery
from dotenv import load_dotenv
from celery.schedules import crontab

# Load environment variables from .env file
load_dotenv()

# Get Redis connection details from environment variables with no defaults
try:
    REDIS_IP = os.environ['REDIS_IP']  # Will raise KeyError if not set
    REDIS_PORT = os.environ['REDIS_PORT']
    REDIS_DB = os.environ['REDIS_DB']
    REDIS_URL = f"redis://{REDIS_IP}:{REDIS_PORT}/{REDIS_DB}"
except KeyError as e:
    missing_var = str(e).strip("'")
    raise EnvironmentError(f"Required environment variable {missing_var} is not set. Check your .env file.")

# Ensure the include list points to the module where tasks are defined
celery_app = Celery(
    'tasks', # Namespace for tasks
    broker=REDIS_URL,
    backend=REDIS_URL, # Use Redis as the result backend too
    include=['portfolio_generator.comprehensive_portfolio_generator', 'tasks']
)

celery_app.conf.timezone = 'Europe/Athens'

# Optional: Add other Celery configurations if needed
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
)

celery_app.conf.timezone = 'Europe/Athens'  # Greek time
celery_app.conf.enable_utc = False  # Use local time

# Standard Celery beat schedule configuration
celery_app.conf.beat_schedule = {
    'generate-portfolio-daily': {
        'task': 'generate_investment_portfolio_task',
        'schedule': crontab(minute=4),   # 06:00 Athens time daily
    },
}