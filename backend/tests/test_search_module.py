"""Automated test suite for Module 9: Unified Global Search"""
import pytest
from datetime import datetime, timezone
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

    # 1. Seed Repos
    r1 = Repository(id=1, name="hacktoberfest-web", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web", platform=PlatformType.WEB)
    r2 = Repository(id=2, name="hacktoberfest-android", github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-android", platform=PlatformType.ANDROID)
    db.add_all([r1, r2])

    # 2. Seed Users
    u1 = User(id=1, name="Aarav Sharma", email="aarav@psit.ac.in", psit_roll_no="2201", erp_verified=True, verified=True, github_username="aarav-sharma", role=UserRole.STUDENT)
    u2 = User(id=2, name="Bhavna Patel", email="bhavna@psit.ac.in", psit_roll_no="2202", erp_verified=True, verified=True, github_username="bhavna-dev", role=UserRole.STUDENT)
    db.add_all([u1, u2])

    # 3. Seed Issues
    i1 = Issue(id=1, repo_id=1, github_issue_id=101, title="Add Dark Mode Switcher", description="Add theme toggle button", difficulty=IssueDifficulty.EASY, category="Frontend UI", tech_tags=["react", "css"], status=IssueStatus.OPEN)
    i2 = Issue(id=2, repo_id=2, github_issue_id=202, title="Fix Memory Leak in Coroutines", description="Garbage collection issue in background tasks", difficulty=IssueDifficulty.HARD, category="Performance", tech_tags=["kotlin", "android"], status=IssueStatus.OPEN)
    db.add_all([i1, i2])

    # 4. Seed PRs
    p1 = PullRequest(id=1, repo_id=1, github_pr_id=501, issue_id=1, user_id=1, title="feat: Dark Mode Switcher implementation", status=PRStatus.OPEN)
    p2 = PullRequest(id=2, repo_id=2, github_pr_id=502, issue_id=2, user_id=2, title="fix: Coroutine cleanup memory fix", status=PRStatus.OPEN)
    db.add_all([p1, p2])

    # 5. Seed Commits
    c1 = Commit(id=1, repo_id=1, user_id=1, github_commit_sha="a1b2c3d4e5f6", message="feat(ui): add dark mode toggle component", committed_at=datetime.now(timezone.utc))
    c2 = Commit(id=2, repo_id=2, user_id=2, github_commit_sha="f6e5d4c3b2a1", message="fix(android): resolve memory leak", committed_at=datetime.now(timezone.utc))
    db.add_all([c1, c2])

    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_unified_search_across_multiple_entities(client_and_db):
    """Test unified multi-entity search returning matches across issues, PRs, and commits."""
    client, _ = client_and_db

    res = client.get("/search?q=Dark Mode")
    assert res.status_code == 200
    data = res.json()

    assert data["query"] == "Dark Mode"
    assert data["total_results"] >= 3

    # Issues check
    assert len(data["issues"]) == 1
    assert data["issues"][0]["github_issue_id"] == 101
    assert data["issues"][0]["repo_name"] == "hacktoberfest-web"

    # PRs check
    assert len(data["pull_requests"]) == 1
    assert data["pull_requests"][0]["github_pr_id"] == 501
    assert data["pull_requests"][0]["author_name"] == "Aarav Sharma"

    # Commits check
    assert len(data["commits"]) == 1
    assert "dark mode" in data["commits"][0]["message"].lower()


def test_search_by_identifier_number(client_and_db):
    """Test searching by numeric issue ID / PR ID."""
    client, _ = client_and_db

    # Search issue #101
    res = client.get("/search?q=101")
    assert res.status_code == 200
    data = res.json()
    assert len(data["issues"]) == 1
    assert data["issues"][0]["github_issue_id"] == 101

    # Search PR #502
    res_pr = client.get("/search?q=502")
    assert res_pr.status_code == 200
    data_pr = res_pr.json()
    assert len(data_pr["pull_requests"]) == 1
    assert data_pr["pull_requests"][0]["github_pr_id"] == 502


def test_search_category_filter(client_and_db):
    """Test scoping search to a single entity type."""
    client, _ = client_and_db

    # 1. Filter by issues only
    res = client.get("/search?q=Dark Mode&category=issues")
    assert res.status_code == 200
    data = res.json()
    assert len(data["issues"]) == 1
    assert len(data["pull_requests"]) == 0
    assert len(data["commits"]) == 0

    # 2. Filter by contributors only
    res_users = client.get("/search?q=Aarav&category=contributors")
    assert res_users.status_code == 200
    data_users = res_users.json()
    assert len(data_users["contributors"]) == 1
    assert data_users["contributors"][0]["name"] == "Aarav Sharma"
    assert data_users["contributors"][0]["github_username"] == "aarav-sharma"

    # 3. Filter by repositories only
    res_repos = client.get("/search?q=android&category=repositories")
    assert res_repos.status_code == 200
    data_repos = res_repos.json()
    assert len(data_repos["repositories"]) == 1
    assert data_repos["repositories"][0]["name"] == "hacktoberfest-android"


def test_search_no_results(client_and_db):
    """Test querying with non-existent term returns zero results safely."""
    client, _ = client_and_db

    res = client.get("/search?q=nonexistentqueryxyz")
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] == 0
    assert data["issues"] == []
    assert data["pull_requests"] == []
    assert data["contributors"] == []
    assert data["repositories"] == []
    assert data["commits"] == []


def test_search_contributor_by_psit_roll_number(client_and_db):
    """v2: Contributors should be findable by their PSIT roll number (institutional ID)."""
    client, _ = client_and_db

    # Aarav's roll number is 2201
    res = client.get("/search?q=2201&category=contributors")
    assert res.status_code == 200
    data = res.json()
    assert len(data["contributors"]) == 1
    assert data["contributors"][0]["name"] == "Aarav Sharma"
    assert data["contributors"][0]["github_username"] == "aarav-sharma"
