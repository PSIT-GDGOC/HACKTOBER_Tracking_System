"""Tests for Module 7: Contributor Profiles"""
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
    PullRequest, PRStatus,
    Claim, ClaimStatus
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
    student1 = User(id=1, name="Vikram Rathore", email="vikram@psit.ac.in", psit_roll_no="2215", erp_verified=True, verified=True, github_username="vikram-dev", role=UserRole.STUDENT)
    student2 = User(id=2, name="Sneha Patel", email="sneha@psit.ac.in", psit_roll_no="2216", erp_verified=True, verified=True, github_username="sneha-p", role=UserRole.STUDENT)

    # Seed repo, issue, contribution, PR
    repo = Repository(id=1, name="web-repo", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web", platform=PlatformType.WEB)
    issue = Issue(id=1, repo_id=1, github_issue_id=101, title="Sample Issue", difficulty=IssueDifficulty.EASY, status=IssueStatus.CLOSED)
    pr = PullRequest(id=1, repo_id=1, github_pr_id=401, issue_id=1, user_id=1, title="feat: sample pr", status=PRStatus.MERGED)
    contrib = Contribution(id=1, user_id=1, issue_id=1, pr_id=1, status=ContributionStatus.MERGED, validation_status=ContributionValidation.VALID)

    db.add_all([student1, student2, repo, issue, pr, contrib])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_public_profile_retrieval(client_and_db):
    client, _ = client_and_db

    # 1. Existing user public profile
    res = client.get("/users/1")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 1
    assert data["name"] == "Vikram Rathore"
    assert data["github_username"] == "vikram-dev"
    assert data["contributions_count"] == 1
    assert data["merged_prs_count"] == 1
    assert "email" not in data  # Privacy protection: sensitive email hidden from public
    assert "psit_roll_no" not in data  # Privacy protection: roll no hidden from public

    # 2. Non-existent user
    res = client.get("/users/9999")
    assert res.status_code == 404


def test_get_own_profile(client_and_db):
    client, _ = client_and_db

    res = client.get("/users/me", headers={"X-User-Id": "1"})
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == 1
    assert data["email"] == "vikram@psit.ac.in"
    assert data["psit_roll_no"] == "2215"
    assert data["verified"] is True  # v2: id/qr card based verification


def test_update_own_profile(client_and_db):
    client, _ = client_and_db

    # 1. Update display name and github username
    res = client.patch(
        "/users/me",
        json={"name": "Vikram R. (Updated)", "github_username": "vikram-coder"},
        headers={"X-User-Id": "1"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Vikram R. (Updated)"
    assert data["github_username"] == "vikram-coder"

    # 2. Attempt to take another student's github_username
    res = client.patch(
        "/users/me",
        json={"github_username": "sneha-p"},
        headers={"X-User-Id": "1"}
    )
    assert res.status_code == 400
    assert "already associated" in res.json()["detail"]
