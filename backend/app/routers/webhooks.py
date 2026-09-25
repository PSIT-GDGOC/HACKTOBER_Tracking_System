import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Header, HTTPException, Request, Depends, status, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.webhook import WebhookResponse
from app.models import WebhookJob, WebhookJobStatus
from app.services.webhook_service import verify_github_signature
from app.services.webhook_job_service import (
    create_webhook_job,
    execute_webhook_job,
    drain_due_webhook_jobs
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/github", response_model=WebhookResponse, summary="GitHub Webhook Receiver")
async def github_webhook_receiver(
    request: Request,
    x_github_event: Optional[str] = Header("ping", alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    db: Session = Depends(get_db),
):
    """
    Primary GitHub Webhook receiver (v2 Architecture - No Celery / No Redis):
    1. Cryptographically verifies HMAC-SHA256 signature against GITHUB_WEBHOOK_SECRET.
    2. Persists payload to Table #11 (`webhook_jobs`) with status 'pending'.
    3. Executes event dispatch through the job engine:
       - 'issues' (status/difficulty/category sync)
       - 'pull_request' (auto-links PRs to claimed issues by GitHub username)
       - 'push' (records commits and links to contributors/issues)
       - 'pull_request_review' (updates contribution state and notifies student)
    4. Automatically handles retries with exponential backoff on transient errors.
    """
    raw_body = await request.body()

    # 1. Signature validation
    if not verify_github_signature(raw_body=raw_body, signature_header=x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub webhook signature. Request rejected."
        )

    # 2. Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {str(e)}"
        )

    action = payload.get("action")

    # 3. Persist incoming webhook event into Table #11 (webhook_jobs)
    job = create_webhook_job(db=db, event_type=x_github_event, payload=payload)

    # 4. Execute through the native job runner
    exec_result = execute_webhook_job(job=job, db=db)

    job_status = job.status.value
    response_status = "success" if job_status == WebhookJobStatus.DONE.value else "failed"

    return WebhookResponse(
        status=response_status,
        event=x_github_event,
        action=action,
        detail=f"Webhook event '{x_github_event}' recorded in webhook_jobs #{job.id} (status: {job_status})",
        data={
            "job_id": job.id,
            "status": job_status,
            "attempts": job.attempts,
            **(exec_result.get("data", {}) if isinstance(exec_result, dict) else {})
        }
    )


@router.post("/jobs/drain", summary="Drain Due Webhook Jobs (Supabase pg_cron Sweep)")
def drain_webhook_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Drains pending or due-for-retry rows from Table #11 (`webhook_jobs`).
    Scheduled via Supabase pg_cron or invoked for manual queue sweeps.
    """
    results = drain_due_webhook_jobs(db=db, batch_size=limit)
    return {
        "status": "success",
        "drained_count": len(results),
        "jobs": results
    }


@router.get("/jobs", summary="List Webhook Jobs")
def list_webhook_jobs(
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db)
):
    """List recent webhook jobs for monitoring and audit logging."""
    query = db.query(WebhookJob)
    if status_filter:
        query = query.filter(WebhookJob.status == status_filter)
    jobs = query.order_by(WebhookJob.created_at.desc()).limit(limit).all()
    return {
        "total": len(jobs),
        "items": [
            {
                "id": j.id,
                "event_type": j.event_type,
                "status": j.status.value,
                "attempts": j.attempts,
                "next_attempt_at": j.next_attempt_at.isoformat() if j.next_attempt_at else None,
                "created_at": j.created_at.isoformat(),
                "error_log": j.error_log
            }
            for j in jobs
        ]
    }
