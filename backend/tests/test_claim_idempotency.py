"""Targeted Verification: Idempotent Claim / Unclaim / Re-Claim Lifecycle.

Covers:
- Claiming an issue creates exactly one Contribution row.
- Unclaiming marks that contribution as RELEASED.
- Re-claiming the same issue reuses the existing row (no duplicates).
- The contribution table never has more than one row per (user_id, issue_id).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import (
    User, UserRole,
    Repository, PlatformType,
    Issue, IssueDifficulty, IssueStatus,
    Contribution, ContributionStatus,
)


@pytest.fixture
def idempotent_setup():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    db = TestingSessionLocal()
    student = User(
        id=1,
        name="Test Student",
        email="test@psit.ac.in",
        psit_roll_no="22001",
        erp_verified=True,
        verified=True,
        github_username="test-student",
        role=UserRole.STUDENT,
    )
    repo = Repository(
        id=1,
        name="test-repo",
        github_repo_url="https://github.com/gdgoc-psit/test-repo",
        platform=PlatformType.WEB,
    )
    issue = Issue(
        id=1,
        repo_id=1,
        github_issue_id=42,
        title="Test Idempotent Issue",
        difficulty=IssueDifficulty.EASY,
        status=IssueStatus.OPEN,
    )
    db.add_all([student, repo, issue])
    db.commit()

    yield client, TestingSessionLocal

    app.dependency_overrides.clear()


def test_claim_creates_single_contribution(idempotent_setup):
    """First claim should create exactly one contribution row."""
    client, session_factory = idempotent_setup

    res = client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    assert res.status_code == 201

    db = session_factory()
    contribs = db.query(Contribution).filter(
        Contribution.user_id == 1, Contribution.issue_id == 1
    ).all()
    assert len(contribs) == 1
    assert contribs[0].status == ContributionStatus.CLAIMED
    db.close()


def test_unclaim_sets_released_status(idempotent_setup):
    """Unclaiming should mark the contribution as RELEASED."""
    client, session_factory = idempotent_setup

    # Claim then unclaim
    client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    unclaim_res = client.post("/issues/1/unclaim", headers={"X-User-Id": "1"})
    assert unclaim_res.status_code == 200

    db = session_factory()
    contribs = db.query(Contribution).filter(
        Contribution.user_id == 1, Contribution.issue_id == 1
    ).all()
    assert len(contribs) == 1
    assert contribs[0].status == ContributionStatus.RELEASED
    db.close()


def test_reclaim_reuses_existing_row(idempotent_setup):
    """Re-claiming after unclaim should reactivate the same row, not create a duplicate."""
    client, session_factory = idempotent_setup

    # Claim -> Unclaim -> Re-claim
    client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    client.post("/issues/1/unclaim", headers={"X-User-Id": "1"})

    # Re-claim the same issue
    reclaim_res = client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    assert reclaim_res.status_code == 201

    db = session_factory()
    contribs = db.query(Contribution).filter(
        Contribution.user_id == 1, Contribution.issue_id == 1
    ).all()
    # Must still be exactly 1 row — the same one reactivated
    assert len(contribs) == 1, f"Expected 1 contribution row, got {len(contribs)}"
    assert contribs[0].status == ContributionStatus.CLAIMED
    db.close()
