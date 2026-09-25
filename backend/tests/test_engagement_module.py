"""Automated test suite for Module 8: Engagement Layer (Leaderboard, Notifications, Activity Feed)"""
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
    Claim, ClaimStatus,
    PullRequest, PRStatus,
    Contribution, ContributionStatus, ContributionValidation,
    Notification,
    ActivityFeed
)
from app.dependencies import get_current_user


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

    # 1. Seed Users (Students + Maintainer)
    s1 = User(
        id=1,
        name="Aarav Sharma",
        email="aarav@psit.ac.in",
        psit_roll_no="2201",
        erp_verified=True,
        verified=True,
        github_username="aarav-sharma",
        role=UserRole.STUDENT,
    )
    s2 = User(
        id=2,
        name="Bhavna Patel",
        email="bhavna@psit.ac.in",
        psit_roll_no="2202",
        erp_verified=True,
        verified=True,
        github_username="bhavna-dev",
        role=UserRole.STUDENT,
    )
    s3 = User(
        id=3,
        name="Chirag Gupta",
        email="chirag@psit.ac.in",
        psit_roll_no="2203",
        erp_verified=True,
        verified=True,
        github_username="chirag-g",
        role=UserRole.STUDENT,
    )
    maint = User(
        id=4,
        name="Aditya Verma",
        email="aditya@psit.ac.in",
        psit_roll_no="2101",
        erp_verified=True,
        verified=True,
        github_username="aditya-maint",
        role=UserRole.MAINTAINER,
    )
    db.add_all([s1, s2, s3, maint])

    # 2. Seed Repositories
    repo_web = Repository(
        id=1,
        name="hacktoberfest-web",
        github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web",
        platform=PlatformType.WEB,
    )
    repo_android = Repository(
        id=2,
        name="hacktoberfest-android",
        github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-android",
        platform=PlatformType.ANDROID,
    )
    db.add_all([repo_web, repo_android])

    # 3. Seed Issues
    # Issue 1: Hard (80 pts) - Web
    iss1 = Issue(
        id=1,
        repo_id=1,
        github_issue_id=101,
        title="Implement OAuth2 Authentication Engine",
        difficulty=IssueDifficulty.HARD,
        status=IssueStatus.CLOSED,
    )
    # Issue 2: Medium (40 pts) - Web
    iss2 = Issue(
        id=2,
        repo_id=1,
        github_issue_id=102,
        title="Refactor State Management with Zustand",
        difficulty=IssueDifficulty.MEDIUM,
        status=IssueStatus.CLOSED,
    )
    # Issue 3: Easy (20 pts) - Android
    iss3 = Issue(
        id=3,
        repo_id=2,
        github_issue_id=103,
        title="Fix Top App Bar Elevation Glitch",
        difficulty=IssueDifficulty.EASY,
        status=IssueStatus.CLOSED,
    )
    # Issue 4: Beginner (10 pts) - Web (Active Claim)
    iss4 = Issue(
        id=4,
        repo_id=1,
        github_issue_id=104,
        title="Update Readme Documentation",
        difficulty=IssueDifficulty.EASY,
        status=IssueStatus.CLAIMED,
    )
    db.add_all([iss1, iss2, iss3, iss4])

    # 4. Seed PRs & Contributions
    # Aarav completed Issue 1 (Hard: 80) and Issue 2 (Medium: 40) => 120 pts
    pr1 = PullRequest(id=1, repo_id=1, github_pr_id=501, issue_id=1, user_id=1, title="PR: OAuth2 Engine", status=PRStatus.MERGED)
    pr2 = PullRequest(id=2, repo_id=1, github_pr_id=502, issue_id=2, user_id=1, title="PR: State Refactor", status=PRStatus.MERGED)
    c1 = Contribution(
        id=1, user_id=1, issue_id=1, pr_id=1,
        status=ContributionStatus.MERGED,
        validation_status=ContributionValidation.VALID,
        timeline_json=[{"status": "merged"}]
    )
    c2 = Contribution(
        id=2, user_id=1, issue_id=2, pr_id=2,
        status=ContributionStatus.MERGED,
        validation_status=ContributionValidation.VALID,
        timeline_json=[{"status": "merged"}]
    )

    # Bhavna completed Issue 3 (Easy: 20 pts) => 20 pts
    pr3 = PullRequest(id=3, repo_id=2, github_pr_id=503, issue_id=3, user_id=2, title="PR: Fix Elevation", status=PRStatus.MERGED)
    c3 = Contribution(
        id=3, user_id=2, issue_id=3, pr_id=3,
        status=ContributionStatus.MERGED,
        validation_status=ContributionValidation.VALID,
        timeline_json=[{"status": "merged"}]
    )

    # Chirag claimed Issue 4, but no merged PR yet => 0 pts
    cl4 = Claim(id=1, issue_id=4, user_id=3, status=ClaimStatus.ACTIVE)
    c4 = Contribution(
        id=4, user_id=3, issue_id=4,
        status=ContributionStatus.CLAIMED,
        validation_status=ContributionValidation.PENDING,
        timeline_json=[{"status": "claimed"}]
    )

    db.add_all([pr1, pr2, pr3, c1, c2, c3, cl4, c4])

    # 5. Seed Notifications
    notif1 = Notification(
        id=1,
        user_id=1,
        type="claim_created",
        payload={"title": "Claimed Issue #101", "issue_id": 1},
        read=True,
        created_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
    )
    notif2 = Notification(
        id=2,
        user_id=1,
        type="pr_merged",
        payload={"title": "🎉 PR Merged!", "pr_id": 1},
        read=False,
        created_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
    )
    notif3 = Notification(
        id=3,
        user_id=2,
        type="pr_merged",
        payload={"title": "🎉 PR Merged!", "pr_id": 3},
        read=False,
        created_at=datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc),
    )
    db.add_all([notif1, notif2, notif3])

    # 6. Seed Activity Feed
    act1 = ActivityFeed(
        id=1,
        type="claim_created",
        actor_id=1,
        target_type="issue",
        target_id=1,
        created_at=datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc),
    )
    act2 = ActivityFeed(
        id=2,
        type="pr_opened",
        actor_id=1,
        target_type="pull_request",
        target_id=1,
        created_at=datetime(2026, 10, 1, 15, 0, tzinfo=timezone.utc),
    )
    act3 = ActivityFeed(
        id=3,
        type="pr_merged",
        actor_id=1,
        target_type="pull_request",
        target_id=1,
        created_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
    )
    db.add_all([act1, act2, act3])

    db.commit()

    yield client, db

    app.dependency_overrides.clear()


# ============================================================================
# Leaderboard Tests
# ============================================================================

def test_leaderboard_rankings_and_points(client_and_db):
    """Test PostgreSQL plain query aggregation computes weighted points and ranks accurately."""
    client, _ = client_and_db

    res = client.get("/leaderboard")
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 3  # 3 students
    entries = data["entries"]
    assert len(entries) == 3

    # Rank 1: Aarav Sharma (80 + 40 = 120 points, 2 merged PRs)
    assert entries[0]["rank"] == 1
    assert entries[0]["name"] == "Aarav Sharma"
    assert entries[0]["total_points"] == 120
    assert entries[0]["merged_prs"] == 2
    assert entries[0]["valid_contributions"] == 2

    # Rank 2: Bhavna Patel (20 points, 1 merged PR)
    assert entries[1]["rank"] == 2
    assert entries[1]["name"] == "Bhavna Patel"
    assert entries[1]["total_points"] == 20
    assert entries[1]["merged_prs"] == 1

    # Rank 3: Chirag Gupta (0 points, 0 merged PRs, 1 claimed issue)
    assert entries[2]["rank"] == 3
    assert entries[2]["name"] == "Chirag Gupta"
    assert entries[2]["total_points"] == 0
    assert entries[2]["claimed_issues"] == 1


def test_leaderboard_pagination_and_repo_filtering(client_and_db):
    """Test leaderboard pagination and filtering by repository."""
    client, _ = client_and_db

    # 1. Pagination: per_page=1
    res = client.get("/leaderboard?page=1&per_page=1")
    assert res.status_code == 200
    data = res.json()
    assert len(data["entries"]) == 1
    assert data["entries"][0]["rank"] == 1
    assert data["entries"][0]["name"] == "Aarav Sharma"

    # Page 2
    res2 = client.get("/leaderboard?page=2&per_page=1")
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["entries"]) == 1
    assert data2["entries"][0]["rank"] == 2
    assert data2["entries"][0]["name"] == "Bhavna Patel"

    # 2. Repo Filter: repo_id=2 (hacktoberfest-android) -> only Bhavna has contributions on repo 2
    res_repo = client.get("/leaderboard?repo_id=2")
    assert res_repo.status_code == 200
    repo_data = res_repo.json()
    # At least Bhavna is listed with points > 0
    bhavna_entry = next((e for e in repo_data["entries"] if e["name"] == "Bhavna Patel"), None)
    assert bhavna_entry is not None
    assert bhavna_entry["total_points"] == 20


# ============================================================================
# Notification Tests
# ============================================================================

def test_get_notifications_unread_first(client_and_db):
    """Test notifications retrieval returns unread notifications first with total/unread counts."""
    client, db = client_and_db

    # Authenticate as Aarav (User 1)
    user1 = db.query(User).filter(User.id == 1).first()
    app.dependency_overrides[get_current_user] = lambda: user1

    res = client.get("/notifications")
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 2
    assert data["unread_count"] == 1
    # First item must be the unread one
    assert data["items"][0]["read"] is False
    assert data["items"][0]["type"] == "pr_merged"
    # Second item is the read one
    assert data["items"][1]["read"] is True
    assert data["items"][1]["type"] == "claim_created"

    # Filter unread only
    res_unread = client.get("/notifications?unread_only=true")
    assert res_unread.status_code == 200
    unread_data = res_unread.json()
    assert len(unread_data["items"]) == 1
    assert unread_data["items"][0]["id"] == 2


def test_mark_notification_read_and_read_all(client_and_db):
    """Test marking individual notification read and marking all read."""
    client, db = client_and_db

    # 1. Authenticate as Aarav (User 1)
    user1 = db.query(User).filter(User.id == 1).first()
    app.dependency_overrides[get_current_user] = lambda: user1

    # Mark notification 2 as read
    patch_res = client.patch("/notifications/2/read")
    assert patch_res.status_code == 200
    assert patch_res.json()["read"] is True

    # Check that unread_count is now 0
    res = client.get("/notifications")
    assert res.json()["unread_count"] == 0

    # 2. Try to mark Bhavna's notification (id=3) as Aarav -> should be 403 Forbidden
    forbidden_res = client.patch("/notifications/3/read")
    assert forbidden_res.status_code == 403

    # 3. Authenticate as Bhavna (User 2) and test read-all
    user2 = db.query(User).filter(User.id == 2).first()
    app.dependency_overrides[get_current_user] = lambda: user2

    assert client.get("/notifications").json()["unread_count"] == 1
    read_all_res = client.post("/notifications/read-all")
    assert read_all_res.status_code == 200
    assert read_all_res.json()["updated_count"] == 1

    # Now Bhavna should have 0 unread
    assert client.get("/notifications").json()["unread_count"] == 0


# ============================================================================
# Activity Feed Tests
# ============================================================================

def test_get_activity_feed_and_filtering(client_and_db):
    """Test global activity event stream and type filtering."""
    client, _ = client_and_db

    res = client.get("/activity")
    assert res.status_code == 200
    data = res.json()

    assert data["total"] == 3
    items = data["items"]
    assert len(items) == 3

    # Newest first (act3 was 12:00, act2 was 15:00, act1 was 09:30)
    # Check enriched actor
    assert items[0]["actor"]["name"] == "Aarav Sharma"
    assert items[0]["actor"]["github_username"] == "aarav-sharma"
    assert items[0]["target"]["type"] in ["pull_request", "pr"]

    # Filter by type=claim_created
    res_claim = client.get("/activity?type=claim_created")
    assert res_claim.status_code == 200
    claim_data = res_claim.json()
    assert claim_data["total"] == 1
    assert claim_data["items"][0]["type"] == "claim_created"
    assert "claimed issue #101" in claim_data["items"][0]["description"]
