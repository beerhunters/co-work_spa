"""
Celery application configuration for background tasks.
"""
from celery import Celery
from config import REDIS_URL
from utils.logger import get_logger

logger = get_logger(__name__)

# Create Celery instance
celery_app = Celery(
    'coworking',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['tasks.newsletter_tasks']
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,

    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata

    # Task execution settings
    task_track_started=True,
    task_time_limit=3600,  # Hard limit: 1 hour
    task_soft_time_limit=3300,  # Soft limit: 55 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,

    # Broker connection settings
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,  # Celery 6.0+ compatibility
    broker_connection_max_retries=10,

    # Worker settings
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,

    # Task routes
    task_routes={
        'tasks.newsletter_tasks.*': {'queue': 'newsletters'},
    },

    # Beat schedule (for periodic tasks)
    beat_schedule={},
)

logger.info("Celery app configured successfully")
