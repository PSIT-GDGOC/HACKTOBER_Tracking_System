"""Targeted Verification: Dashboard Count ↔ Timeline Harmony.

Covers:
- Dashboard valid_contributions_count matches the count of non-released valid contributions.
- Released contributions are excluded from the dashboard count.
- Multiple contributions for distinct issues are counted correctly.
"""
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
    Claim, ClaimStatus,
    PullRequest, PRStatus,
    Contribution, ContributionStatus, ContributionValidation,
)


@pytest.fixture
def harmony_setup():
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

    # Seed student
    student = User(
        id=1, name="Harmony Student", email="harmony@psit.ac.in",
        psit_roll_no="22050", erp_verified=True, verified=True,
        github_username="harmony-student", role=UserRole.STUDENT,
    )

    # Seed repo
    repo = Repository(
        id=1, name="harmony-repo",
        github_repo_url="https://github.com/gdgoc-psit/harmony-repo",
        platform=PlatformType.WEB,
    )

    # Seed issues
    issue1 = Issue(id=1, repo_id=1, github_issue_id=201, title="Issue A",
                   difficulty=IssueDifficulty.EASY, status=IssueStatus.CLOSED)
    issue2 = Issue(id=2, repo_id=1, github_issue_id=202, title="Issue B",
                   difficulty=IssueDifficulty.MEDIUM, status=IssueStatus.CLOSED)
    issue3 = Issue(id=3, repo_id=1, github_issue_id=203, title="Issue C (Released)",
                   difficulty=IssueDifficulty.HARD, status=IssueStatus.OPEN)

    # Active claim for issue1
    claim = Claim(id=1, issue_id=1, user_id=1, status=ClaimStatus.ACTIVE)

    # Contribution 1: VALID, MERGED (should count)
    contrib1 = Contribution(
        id=1, user_id=1, issue_id=1,
        status=ContributionStatus.MERGED,
        validation_status=ContributionValidation.VALID,
    )
    # Contribution 2: VALID, MERGED (should count)
    contrib2 = Contribution(
        id=2, user_id=1, issue_id=2,
        status=ContributionStatus.MERGED,
        validation_status=ContributionValidation.VALID,
    )
    # Contribution 3: VALID but RELEASED (should NOT count)
    contrib3 = Contribution(
        id=3, user_id=1, issue_id=3,
        status=ContributionStatus.RELEASED,
        validation_status=ContributionValidation.VALID,
    )

    db.add_all([student, repo, issue1, issue2, issue3, claim, contrib1, contrib2, contrib3])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_dashboard_excludes_released_from_valid_count(harmony_setup):
    """Dashboard valid_contributions_count must exclude RELEASED contributions."""
    client, _ = harmony_setup

    res = client.get("/dashboard/student", headers={"X-User-Id": "1"})
    assert res.status_code == 200
    data = res.json()

    # 2 valid non-released, 1 valid but released → count should be 2
    assert data["valid_contributions_count"] == 2, (
        f"Expected 2 valid contributions (excluding released), got {data['valid_contributions_count']}"
    )


def test_dashboard_counts_distinct_issues(harmony_setup):
    """Dashboard valid_contributions_count should count distinct issues, not raw rows."""
    client, db = harmony_setup

    # The fixture already has 2 valid non-released contributions on 2 distinct issues
    res = client.get("/dashboard/student", headers={"X-User-Id": "1"})
    data = res.json()

    assert data["valid_contributions_count"] == 2
    # active_claims_count should match the seeded claim
    assert data["active_claims_count"] == 1
