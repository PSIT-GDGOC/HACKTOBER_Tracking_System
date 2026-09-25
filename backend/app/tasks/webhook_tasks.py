import logging
from app.celery_app import celery_app
from app.db import SessionLocal
from app.services.webhook_service import process_webhook_event

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="process_github_webhook_task",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def process_github_webhook_task(self, event_type: str, payload: dict) -> dict:
    """
    Celery background worker task for processing GitHub webhooks asynchronously.
    Runs with PostgreSQL as the message broker.
    Catches transient failures and retries up to 3 times with exponential backoff.
    """
    logger.info(f"Processing webhook task {self.request.id} for event '{event_type}' (attempt {self.request.retries + 1})")
    db = SessionLocal()
    try:
        result = process_webhook_event(event_type=event_type, payload=payload, db=db)
        logger.info(f"Successfully processed webhook task {self.request.id}: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error processing webhook event '{event_type}': {exc}")
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
