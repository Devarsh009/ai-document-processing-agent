from celery import Celery
from app.config import settings

celery_app = Celery(
    "document_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Critical: import tasks so Celery registers them on startup
import app.workers.tasks  # noqa: E402, F401
