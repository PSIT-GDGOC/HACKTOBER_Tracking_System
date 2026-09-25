"""Tests for Module 2: Issue Management and Claim System"""
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
    Claim, ClaimStatus
)


@pytest.fixture
def client_and_db():
    # In-memory SQLite for testing
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
    student1 = User(id=1, name="Student 1", email="s1@psit.ac.in", psit_roll_no="2201", erp_verified=True, verified=True, role=UserRole.STUDENT)
    student2 = User(id=2, name="Student 2", email="s2@psit.ac.in", psit_roll_no="2202", erp_verified=True, verified=True, role=UserRole.STUDENT)
    unverified = User(id=3, name="Unverified", email="unver@psit.ac.in", psit_roll_no="2203", erp_verified=False, verified=False, role=UserRole.STUDENT)
    maintainer = User(id=4, name="Maintainer", email="maint@psit.ac.in", psit_roll_no="2204", erp_verified=True, verified=True, role=UserRole.MAINTAINER)

    # Seed repository & issues
    repo = Repository(id=1, name="web-repo", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web", platform=PlatformType.WEB)
    issue1 = Issue(id=1, repo_id=1, github_issue_id=101, title="Navbar Issue", difficulty=IssueDifficulty.EASY, category="frontend", tech_tags=["React"], labels=["easy"], status=IssueStatus.OPEN)
    issue2 = Issue(id=2, repo_id=1, github_issue_id=102, title="Footer Issue", difficulty=IssueDifficulty.MEDIUM, category="frontend", tech_tags=["React"], labels=["medium"], status=IssueStatus.OPEN)
    issue3 = Issue(id=3, repo_id=1, github_issue_id=103, title="Backend Issue", difficulty=IssueDifficulty.HARD, category="backend", tech_tags=["Python"], labels=["hard"], status=IssueStatus.OPEN)

    db.add_all([student1, student2, unverified, maintainer, repo, issue1, issue2, issue3])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_list_issues_and_filtering(client_and_db):
    client, _ = client_and_db

    # List all issues
    res = client.get("/issues")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # Filter by difficulty
    res = client.get("/issues?difficulty=easy")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Navbar Issue"

    # Filter by category
    res = client.get("/issues?category=backend")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Backend Issue"


def test_claim_flow_and_restrictions(client_and_db):
    client, _ = client_and_db

    # 1. Unverified student cannot claim
    res = client.post("/issues/1/claim", headers={"X-User-Id": "3"})
    assert res.status_code == 403
    assert "verified" in res.json()["detail"].lower()

    # 2. Verified student claims issue 1
    res = client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    assert res.status_code == 201
    claim_info = res.json()
    assert claim_info["issue_id"] == 1
    assert claim_info["status"] == "active"
    assert claim_info["user"]["psit_roll_no"] == "2201"

    # 3. Issue is now marked claimed
    res = client.get("/issues/1")
    assert res.status_code == 200
    assert res.json()["status"] == "claimed"
    assert res.json()["active_claim"]["user_id"] == 1

    # 4. Another student cannot claim an already claimed issue
    res = client.post("/issues/1/claim", headers={"X-User-Id": "2"})
    assert res.status_code in [400, 409]

    # 5. Student 1 claims issue 2 (reaches max limit of 2)
    res = client.post("/issues/2/claim", headers={"X-User-Id": "1"})
    assert res.status_code == 201

    # 6. Student 1 tries to claim issue 3 (violates max limit of 2)
    res = client.post("/issues/3/claim", headers={"X-User-Id": "1"})
    assert res.status_code == 400
    assert "limit" in res.json()["detail"].lower()


def test_unclaim_flow(client_and_db):
    client, _ = client_and_db

    # Student 1 claims issue 1
    res = client.post("/issues/1/claim", headers={"X-User-Id": "1"})
    assert res.status_code == 201

    # Student 2 tries to unclaim Student 1's issue (unauthorized)
    res = client.post("/issues/1/unclaim", headers={"X-User-Id": "2"})
    assert res.status_code == 403

    # Student 1 unclaims their own issue
    res = client.post("/issues/1/unclaim", headers={"X-User-Id": "1"})
    assert res.status_code == 200
    assert res.json()["status"] == "released"

    # Verify issue 1 is back to OPEN
    res = client.get("/issues/1")
    assert res.json()["status"] == "open"

    # Now Student 2 can claim issue 1
    res = client.post("/issues/1/claim", headers={"X-User-Id": "2"})
    assert res.status_code == 201
    assert res.json()["user"]["psit_roll_no"] == "2202"
