"""Tests for Module 6: Dashboard Aggregations"""
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
    Commit,
    Contribution, ContributionStatus, ContributionValidation,
    Review, ReviewStatus
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
    # Seed users
    student = User(id=1, name="Pooja Sharma", email="pooja@psit.ac.in", psit_roll_no="2210", erp_verified=True, verified=True, role=UserRole.STUDENT)
    maintainer = User(id=2, name="Lead Dev", email="lead@psit.ac.in", psit_roll_no="2110", erp_verified=True, verified=True, role=UserRole.MAINTAINER)

    # Seed repositories
    web_repo = Repository(id=1, name="web-repo", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web", platform=PlatformType.WEB)
    android_repo = Repository(id=2, name="android-repo", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-android", platform=PlatformType.ANDROID)

    # Seed issues
    issue1 = Issue(id=1, repo_id=1, github_issue_id=101, title="Web Issue 1", difficulty=IssueDifficulty.EASY, status=IssueStatus.CLAIMED)
    issue2 = Issue(id=2, repo_id=1, github_issue_id=102, title="Web Issue 2", difficulty=IssueDifficulty.HARD, status=IssueStatus.OPEN)

    # Seed claim
    claim = Claim(id=1, issue_id=1, user_id=1, status=ClaimStatus.ACTIVE)

    # Seed PRs
    pr1 = PullRequest(id=1, repo_id=1, github_pr_id=301, issue_id=1, user_id=1, title="feat: issue 1 pr", status=PRStatus.OPEN)
    pr2 = PullRequest(id=2, repo_id=1, github_pr_id=302, issue_id=2, user_id=1, title="feat: issue 2 pr", status=PRStatus.MERGED)

    # Seed Commit
    now = datetime.now(timezone.utc)
    c1 = Commit(id=1, repo_id=1, github_commit_sha="sha_999", user_id=1, message="feat: commit 1", committed_at=now)

    # Seed Contribution
    contrib = Contribution(id=1, user_id=1, issue_id=1, status=ContributionStatus.PR_SUBMITTED, validation_status=ContributionValidation.VALID)

    # Seed Review
    rev = Review(id=1, pr_id=1, reviewer_id=2, status=ReviewStatus.COMMENTED, comment="Please refine tests")

    db.add_all([student, maintainer, web_repo, android_repo, issue1, issue2, claim, pr1, pr2, c1, contrib, rev])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_student_dashboard(client_and_db):
    client, _ = client_and_db

    res = client.get("/dashboard/student", headers={"X-User-Id": "1"})
    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == 1
    assert data["name"] == "Pooja Sharma"
    assert data["active_claims_count"] == 1
    assert len(data["active_claims"]) == 1
    assert data["active_claims"][0]["issue_title"] == "Web Issue 1"
    assert data["prs_submitted_count"] == 2
    assert data["prs_merged_count"] == 1
    assert data["valid_contributions_count"] == 1


def test_maintainer_dashboard(client_and_db):
    client, _ = client_and_db

    res = client.get("/dashboard/maintainer", headers={"X-User-Id": "2"})
    assert res.status_code == 200
    data = res.json()
    assert data["maintainer_id"] == 2
    assert data["pending_reviews_count"] == 1
    assert len(data["review_queue"]) == 1
    assert data["review_queue"][0]["title"] == "feat: issue 1 pr"
    assert len(data["recently_reviewed"]) == 1
    assert data["recently_reviewed"][0]["comment"] == "Please refine tests"


def test_repository_dashboard(client_and_db):
    client, _ = client_and_db

    # Existing repo
    res = client.get("/dashboard/repository/1")
    assert res.status_code == 200
    data = res.json()
    assert data["repository"]["name"] == "web-repo"
    assert data["total_issues"] == 2
    assert data["open_issues"] == 1
    assert data["claimed_issues"] == 1
    assert data["total_prs"] == 2
    assert data["open_prs"] == 1
    assert data["merged_prs"] == 1
    assert data["total_commits"] == 1
    assert data["unique_contributors_count"] == 1

    # Non-existent repo
    res = client.get("/dashboard/repository/9999")
    assert res.status_code == 404


def test_admin_dashboard(client_and_db):
    client, _ = client_and_db

    res = client.get("/dashboard/admin")
    assert res.status_code == 200
    data = res.json()
    assert data["total_registered_students"] == 1
    assert data["verified_students"] == 2
    assert data["total_issues"] == 2
    assert data["active_claims"] == 1
    assert data["total_prs_submitted"] == 2
    assert data["total_prs_merged"] == 1
    assert data["total_commits"] == 1
    assert len(data["repositories_overview"]) == 2
