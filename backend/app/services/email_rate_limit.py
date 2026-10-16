"""Atomic sliding-window reservations shared by PostgreSQL/SQLite workers."""
import hashlib
import hmac
import math
import time

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email_rate_limit import EmailRateLimit


def check_email_rate_limit(
    email: str, db: Session, *, scope: str = "email", limit: int = 5, cooldown: int = 60,
) -> None:
    """Reserve before lookup/delivery; failures and unknown accounts consume quota.

    Uses an independent transaction so delivery rollback cannot refund requests.
    An upsert takes a write lock (also on SQLite); PostgreSQL additionally locks
    the row before reading its history. No process-local state or fixture bypass.
    """
    key = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{scope}:{email.strip().lower()}".encode(), hashlib.sha256,
    ).hexdigest()
    with Session(db.get_bind()) as reservation:
        with reservation.begin():
            insert = sqlite_insert if reservation.bind.dialect.name == "sqlite" else pg_insert
            # Cleanup is indexed and keeps inactive identifiers out of the store.
            now = time.time()
            reservation.execute(delete(EmailRateLimit).where(EmailRateLimit.expires_at <= now))
            reservation.execute(
                insert(EmailRateLimit).values(key=key, timestamps=[], expires_at=now + 3600)
                .on_conflict_do_nothing(index_elements=["key"])
            )
            bucket = reservation.execute(
                select(EmailRateLimit).where(EmailRateLimit.key == key).with_for_update()
            ).scalar_one()
            now = time.time()
            history = [stamp for stamp in bucket.timestamps if stamp > now - 3600]
            retry_after = 0
            if history and now - history[-1] < cooldown:
                retry_after = math.ceil(cooldown - (now - history[-1]))
            if len(history) >= limit:
                retry_after = max(retry_after, math.ceil(history[0] + 3600 - now))
            if retry_after:
                raise HTTPException(
                    status_code=429,
                    detail=f"Please wait {retry_after} seconds before requesting another email.",
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.timestamps = history + [now]
            bucket.expires_at = now + 3600
