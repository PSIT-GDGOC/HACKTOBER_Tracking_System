"""Tests for Module 5: Contribution State Machine & Timeline"""
from datetime import datetime, timezone
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
    Contribution, ContributionStatus, ContributionValidation,
    PullRequest, PRStatus
)


@pytest.fixture
def client_and_db():
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
    # Seed user
    student = User(id=1, name="Kavya Singh", email="kavya@psit.ac.in", psit_roll_no="2209", erp_verified=True, verified=True, github_username="kavya-s", role=UserRole.STUDENT)
    moderator = User(id=2, name="Admin Lead", email="admin@psit.ac.in", psit_roll_no="2109", erp_verified=True, verified=True, role=UserRole.ADMIN)

    # Seed repository & issue
    repo = Repository(id=1, name="hacktoberfest-web", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web", platform=PlatformType.WEB)
    issue1 = Issue(id=1, repo_id=1, github_issue_id=101, title="Accessibility improvements", difficulty=IssueDifficulty.MEDIUM, status=IssueStatus.CLAIMED)
    issue2 = Issue(id=2, repo_id=1, github_issue_id=102, title="SEO meta tags", difficulty=IssueDifficulty.EASY, status=IssueStatus.OPEN)

    now = datetime.now(timezone.utc)
    contrib1 = Contribution(
        id=1,
        user_id=1,
        issue_id=1,
        status=ContributionStatus.CLAIMED,
        validation_status=ContributionValidation.PENDING,
        timeline_json=[{"status": "claimed", "timestamp": now.isoformat(), "detail": "Claimed issue #101"}]
    )

    db.add_all([student, moderator, repo, issue1, issue2, contrib1])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_state_machine_valid_progression(client_and_db):
    client, db = client_and_db

    # 1. claimed -> in_progress
    res = client.patch("/contributions/1/status?new_status=in_progress")
    assert res.status_code == 200
    assert res.json()["status"] == "in_progress"

    # 2. in_progress -> pr_submitted
    res = client.patch("/contributions/1/status?new_status=pr_submitted")
    assert res.status_code == 200
    assert res.json()["status"] == "pr_submitted"

    # 3. pr_submitted -> under_review
    res = client.patch("/contributions/1/status?new_status=under_review")
    assert res.status_code == 200
    assert res.json()["status"] == "under_review"

    # 4. under_review -> changes_requested
    res = client.patch("/contributions/1/status?new_status=changes_requested")
    assert res.status_code == 200
    assert res.json()["status"] == "changes_requested"

    # 5. changes_requested -> pr_submitted (after pushing updates)
    res = client.patch("/contributions/1/status?new_status=pr_submitted")
    assert res.status_code == 200

    # 6. pr_submitted -> accepted
    res = client.patch("/contributions/1/status?new_status=accepted")
    assert res.status_code == 200

    # 7. accepted -> merged
    res = client.patch("/contributions/1/status?new_status=merged")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "merged"
    assert data["validation_status"] == "valid"


def test_state_machine_invalid_transition_rejected(client_and_db):
    client, _ = client_and_db

    # Attempt invalid jump: claimed -> merged directly
    res = client.patch("/contributions/1/status?new_status=merged")
    assert res.status_code == 400
    assert "Invalid state transition" in res.json()["detail"]


def test_user_contribution_timeline_retrieval(client_and_db):
    client, _ = client_and_db

    res = client.get("/contributions/1")
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == 1
    assert data["total_contributions"] == 1
    assert data["in_progress_count"] == 1
    assert data["valid_contributions_count"] == 0
    assert len(data["items"][0]["timeline_json"]) >= 1


def test_moderation_validation_status_update(client_and_db):
    client, db = client_and_db

    # Moderator marks contribution as duplicate
    res = client.patch(
        "/contributions/1/validation",
        json={"validation_status": "duplicate", "note": "Duplicate submission of PR #40"},
        headers={"X-User-Id": "2"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["validation_status"] == "duplicate"

    # Verify timeline records the moderation note
    timeline = data["timeline_json"]
    last_event = timeline[-1]
    assert "duplicate" in last_event.get("validation_change", "")
    assert "Duplicate submission" in last_event.get("detail", "")
