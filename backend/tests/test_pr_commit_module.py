"""Tests for Module 4: Pull Request & Commit Tracking Module"""
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
    PullRequest, PRStatus,
    Commit,
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
    student1 = User(id=1, name="Student One", email="s1@psit.ac.in", psit_roll_no="2201", erp_verified=True, verified=True, github_username="student-1", role=UserRole.STUDENT)
    student2 = User(id=2, name="Student Two", email="s2@psit.ac.in", psit_roll_no="2202", erp_verified=True, verified=True, github_username="student-2", role=UserRole.STUDENT)
    maintainer = User(id=3, name="Maintainer", email="m@psit.ac.in", psit_roll_no="2101", erp_verified=True, verified=True, github_username="maintainer-lead", role=UserRole.MAINTAINER)

    # Seed repositories
    repo1 = Repository(id=1, name="hacktoberfest-web", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web", platform=PlatformType.WEB)
    repo2 = Repository(id=2, name="hacktoberfest-android", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-android", platform=PlatformType.ANDROID)

    # Seed issues
    issue1 = Issue(id=1, repo_id=1, github_issue_id=101, title="Web Issue", difficulty=IssueDifficulty.EASY, status=IssueStatus.IN_PROGRESS)
    issue2 = Issue(id=2, repo_id=2, github_issue_id=201, title="Android Issue", difficulty=IssueDifficulty.MEDIUM, status=IssueStatus.OPEN)

    # Seed PRs
    pr1 = PullRequest(id=1, repo_id=1, github_pr_id=501, issue_id=1, user_id=1, title="feat: web fix", status=PRStatus.OPEN, reviewer_id=3)
    pr2 = PullRequest(id=2, repo_id=2, github_pr_id=502, issue_id=2, user_id=2, title="feat: android fix", status=PRStatus.MERGED, reviewer_id=3)

    # Seed Reviews
    rev1 = Review(id=1, pr_id=1, reviewer_id=3, status=ReviewStatus.COMMENTED, comment="Looking good!")

    # Seed Commits
    now = datetime.now(timezone.utc)
    c1 = Commit(id=1, repo_id=1, github_commit_sha="sha_111", user_id=1, message="feat: initial commit", issue_id=1, pr_id=1, committed_at=now)
    c2 = Commit(id=2, repo_id=1, github_commit_sha="sha_222", user_id=1, message="docs: update readme", issue_id=1, pr_id=1, committed_at=now)
    c3 = Commit(id=3, repo_id=2, github_commit_sha="sha_333", user_id=2, message="feat: compose layout", issue_id=2, pr_id=2, committed_at=now)

    db.add_all([student1, student2, maintainer, repo1, repo2, issue1, issue2, pr1, pr2, rev1, c1, c2, c3])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_list_pull_requests_and_filters(client_and_db):
    client, _ = client_and_db

    # 1. List all PRs
    res = client.get("/pull-requests")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # 2. Filter by repo_id
    res = client.get("/pull-requests?repo_id=1")
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["title"] == "feat: web fix"

    # 3. Filter by status
    res = client.get("/pull-requests?status=merged")
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["status"] == "merged"

    # 4. Filter by contributor github_username
    res = client.get("/pull-requests?github_username=student-1")
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["user"]["github_username"] == "student-1"


def test_get_single_pull_request(client_and_db):
    client, _ = client_and_db

    # Existing PR
    res = client.get("/pull-requests/1")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 1
    assert data["title"] == "feat: web fix"
    assert data["linked_issue"]["title"] == "Web Issue"
    assert data["repository"]["name"] == "hacktoberfest-web"
    assert len(data["reviews"]) == 1
    assert data["reviews"][0]["comment"] == "Looking good!"

    # Non-existent PR
    res = client.get("/pull-requests/9999")
    assert res.status_code == 404


def test_list_commits_and_filters(client_and_db):
    client, _ = client_and_db

    # 1. List all commits
    res = client.get("/commits")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # 2. Filter commits by repo_id
    res = client.get("/commits?repo_id=1")
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # 3. Filter commits by contributor
    res = client.get("/commits?github_username=student-2")
    assert res.status_code == 200
    assert res.json()["total"] == 1
    assert res.json()["items"][0]["github_commit_sha"] == "sha_333"

    # 4. Filter commits by pr_id
    res = client.get("/commits?pr_id=1")
    assert res.status_code == 200
    assert res.json()["total"] == 2
