import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import WebhookJob, WebhookJobStatus
from app.services.webhook_service import process_webhook_event

logger = logging.getLogger(__name__)


def create_webhook_job(db: Session, event_type: str, payload: Dict[str, Any]) -> WebhookJob:
    """Insert incoming GitHub webhook event into Table #11 (webhook_jobs) with PENDING status."""
    now = datetime.now(timezone.utc)
    job = WebhookJob(
        event_type=event_type,
        payload_json=payload,
        status=WebhookJobStatus.PENDING,
        attempts=0,
        next_attempt_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def execute_webhook_job(job: WebhookJob, db: Session) -> Dict[str, Any]:
    """Execute a single webhook job through the event dispatcher.
    Handles success state transition and exponential backoff retry scheduling on failure.
    """
    job.status = WebhookJobStatus.PROCESSING
    job.attempts += 1
    db.commit()

    try:
        result = process_webhook_event(
            event_type=job.event_type,
            payload=job.payload_json,
            db=db
        )
        job.status = WebhookJobStatus.DONE
        job.error_log = None
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        return result
    except Exception as exc:
        logger.error(f"Error processing webhook job #{job.id} ('{job.event_type}'): {exc}", exc_info=True)
        db.rollback()
        # Exponential backoff: 60s, 120s, 240s, 480s, capped at max 5 attempts
        backoff_seconds = 60 * (2 ** min(job.attempts - 1, 4))
        job.status = WebhookJobStatus.FAILED
        job.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
        job.error_log = str(exc)
        job.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "status": "failed",
            "job_id": job.id,
            "attempts": job.attempts,
            "next_attempt_at": job.next_attempt_at.isoformat(),
            "error": str(exc),
        }


def drain_due_webhook_jobs(db: Session, batch_size: int = 20) -> List[Dict[str, Any]]:
    """Drains pending or due-for-retry webhook jobs.
    Called by Supabase pg_cron sweep or manual maintenance trigger.
    """
    now = datetime.now(timezone.utc)
    due_jobs = (
        db.query(WebhookJob)
        .filter(
            or_(
                WebhookJob.status == WebhookJobStatus.PENDING,
                WebhookJob.status == WebhookJobStatus.FAILED,
            ),
            WebhookJob.next_attempt_at <= now,
            WebhookJob.attempts < 5,
        )
        .order_by(WebhookJob.next_attempt_at.asc())
        .limit(batch_size)
        .all()
    )

    results = []
    for job in due_jobs:
        res = execute_webhook_job(job, db)
        results.append({"job_id": job.id, "status": job.status.value, "result": res})

    return results
