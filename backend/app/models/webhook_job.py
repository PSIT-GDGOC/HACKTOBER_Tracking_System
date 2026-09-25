import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, JSON, Index
from app.db import Base


class WebhookJobStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class WebhookJob(Base):
    __tablename__ = "webhook_jobs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, default="unknown", index=True)
    payload_json = Column(JSON, nullable=False)
    status = Column(
        Enum(WebhookJobStatus, values_callable=lambda x: [e.value for e in x], name="webhookjobstatus"),
        default=WebhookJobStatus.PENDING,
        nullable=False,
        index=True
    )
    attempts = Column(Integer, default=0, nullable=False)
    next_attempt_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    error_log = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_webhook_jobs_status_next_attempt", "status", "next_attempt_at"),
    )
