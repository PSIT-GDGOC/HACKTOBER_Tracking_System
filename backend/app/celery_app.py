from celery import Celery
from app.config import settings

# Celery application configured with PostgreSQL as message broker & result backend
# Per architecture specification: No Redis, lean two-service infrastructure footprint.
# Uses property-based URLs to handle Supabase postgres:// -> sqla+postgresql:// rewrite.
celery_app = Celery(
    "hacktoberfest_tasks",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,        # 5 minutes hard limit
    task_soft_time_limit=240,   # 4 minutes soft limit
)
