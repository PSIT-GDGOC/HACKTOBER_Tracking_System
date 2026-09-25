import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import (
    User, UserRole, VerificationMethod,
    WebhookJob, WebhookJobStatus
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_v2_user_verification_fields(db_session):
    now = datetime.now(timezone.utc)
    user = User(
        name="Rohit Gupta",
        email="rohit.2200320100099@psit.ac.in",
        psit_roll_no="2200320100099",
        id_card_image_url="private/id_cards/rohit_2200320100099.png",
        qr_token="psit://verify/student/2200320100099/token_xyz789",
        portal_snapshot_json={
            "name": "Rohit Gupta",
            "roll_no": "2200320100099",
            "department": "IT",
            "status": "active"
        },
        verification_method=VerificationMethod.QR_AUTO,
        verified=True,
        verified_at=now,
        github_username="rohit-gupta-psit",
        role=UserRole.STUDENT,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.verified is True
    assert user.verification_method == VerificationMethod.QR_AUTO
    assert user.id_card_image_url == "private/id_cards/rohit_2200320100099.png"
    assert user.qr_token == "psit://verify/student/2200320100099/token_xyz789"
    assert user.portal_snapshot_json["department"] == "IT"
    assert user.erp_verified is True  # backwards compatible alias


def test_v2_webhook_job_creation_and_lifecycle(db_session):
    now = datetime.now(timezone.utc)
    job = WebhookJob(
        event_type="pull_request",
        payload_json={"action": "opened", "pull_request": {"number": 42}},
        status=WebhookJobStatus.PENDING,
        attempts=0,
        next_attempt_at=now,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.id is not None
    assert job.status == WebhookJobStatus.PENDING
    assert job.event_type == "pull_request"
    assert job.attempts == 0
    assert job.payload_json["pull_request"]["number"] == 42

    # Simulate processing failure and backoff
    job.status = WebhookJobStatus.FAILED
    job.attempts += 1
    job.next_attempt_at = now + timedelta(seconds=60)
    job.error_log = "Simulated downstream timeout"
    db_session.commit()
    db_session.refresh(job)

    assert job.status == WebhookJobStatus.FAILED
    assert job.attempts == 1
    assert "timeout" in job.error_log

    # Simulate retry success
    job.status = WebhookJobStatus.DONE
    db_session.commit()
    db_session.refresh(job)

    assert job.status == WebhookJobStatus.DONE
