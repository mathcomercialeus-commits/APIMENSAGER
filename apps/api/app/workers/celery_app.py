from celery import Celery

from app.core.config import settings
from app.core.logging import configure_logging


configure_logging(settings.debug)


celery_app = Celery(
    "atendecrm_saas",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
)

celery_app.conf.update(
    accept_content=["json"],
    broker_connection_retry_on_startup=True,
    enable_utc=True,
    imports=("app.workers.tasks",),
    result_expires=3600,
    result_serializer="json",
    task_always_eager=settings.celery_task_always_eager,
    task_default_queue=settings.celery_default_queue,
    task_ignore_result=True,
    task_serializer="json",
    timezone="UTC",
    worker_prefetch_multiplier=1,
)
