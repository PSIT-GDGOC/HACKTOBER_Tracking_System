"""Tests for Module 3: GitHub Webhook Sync Engine (v2 — webhook_jobs table, no Celery)"""
import hashlib
import hmac
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
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
    Review, ReviewStatus,
    Notification,
    WebhookJob, WebhookJobStatus,
)


def _generate_signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


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
    student = User(
        id=1,
        name="Aarav Sharma",
        email="aarav@psit.ac.in",
        psit_roll_no="2201",
        verified=True,
        github_username="aarav-sharma",
        role=UserRole.STUDENT
    )
    maintainer = User(
        id=2,
        name="Aditya Verma",
        email="aditya@psit.ac.in",
        psit_roll_no="2101",
        verified=True,
        github_username="aditya-maint",
        role=UserRole.MAINTAINER
    )
    repo = Repository(
        id=1,
        name="hacktoberfest-web",
        github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web",
        platform=PlatformType.WEB
    )
    issue = Issue(
        id=1,
        repo_id=1,
        github_issue_id=101,
        title="Add Dark Mode Toggle",
        difficulty=IssueDifficulty.EASY,
        status=IssueStatus.CLAIMED
    )
    claim = Claim(
        id=1,
        issue_id=1,
        user_id=1,
        status=ClaimStatus.ACTIVE
    )
    contrib = Contribution(
        id=1,
        user_id=1,
        issue_id=1,
        status=ContributionStatus.CLAIMED,
        validation_status=ContributionValidation.PENDING,
        timeline_json=[{"status": "claimed"}]
    )

    db.add_all([student, maintainer, repo, issue, claim, contrib])
    db.commit()

    yield client, db

    app.dependency_overrides.clear()


def test_webhook_signature_verification(client_and_db, monkeypatch):
    client, _ = client_and_db
    test_secret = "super-secret-key-123"
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", test_secret)

    payload = {"zen": "Non-blocking is better than blocking."}
    body_bytes = json.dumps(payload).encode("utf-8")

    # 1. Invalid signature should be rejected with 401
    bad_headers = {
        "X-GitHub-Event": "ping",
        "X-Hub-Signature-256": "sha256=invalidhexsignature0000000000000000000000000000000000000000000000",
        "Content-Type": "application/json"
    }
    res = client.post("/webhooks/github", data=body_bytes, headers=bad_headers)
    assert res.status_code == 401
    assert "Invalid GitHub webhook signature" in res.json()["detail"]

    # 2. Valid signature should be accepted
    valid_sig = _generate_signature(body_bytes, test_secret)
    good_headers = {
        "X-GitHub-Event": "ping",
        "X-Hub-Signature-256": valid_sig,
        "Content-Type": "application/json"
    }
    res = client.post("/webhooks/github", data=body_bytes, headers=good_headers)
    assert res.status_code == 200
    assert "ping" in res.json()["event"]


def test_pull_request_opened_and_auto_link(client_and_db, monkeypatch):
    client, db = client_and_db
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")  # Bypass sig check for payload test

    pr_payload = {
        "action": "opened",
        "repository": {"name": "hacktoberfest-web", "html_url": "https://github.com/gdgoc-psit/hacktoberfest-web"},
        "pull_request": {
            "id": 9991,
            "number": 42,
            "title": "feat: dark mode switcher",
            "merged": False,
            "user": {"login": "aarav-sharma"}
        }
    }

    res = client.post(
        "/webhooks/github",
        json=pr_payload,
        headers={"X-GitHub-Event": "pull_request"}
    )
    assert res.status_code == 200

    # Verify webhook_job was created in Table #11
    job = db.query(WebhookJob).filter(WebhookJob.event_type == "pull_request").first()
    assert job is not None
    assert job.status == WebhookJobStatus.DONE
    assert job.attempts == 1

    # Verify PR created and auto-linked to issue 1
    pr = db.query(PullRequest).filter(PullRequest.github_pr_id == 9991).first()
    assert pr is not None
    assert pr.issue_id == 1
    assert pr.user_id == 1

    # Verify Issue transitioned to in_progress
    issue = db.query(Issue).filter(Issue.id == 1).first()
    assert issue.status == IssueStatus.IN_PROGRESS

    # Verify Contribution transitioned to pr_submitted
    contrib = db.query(Contribution).filter(Contribution.issue_id == 1).first()
    assert contrib.status == ContributionStatus.PR_SUBMITTED
    assert contrib.pr_id == pr.id


def test_pull_request_review_event(client_and_db, monkeypatch):
    client, db = client_and_db
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")

    # First open PR
    pr = PullRequest(id=1, repo_id=1, github_pr_id=9991, issue_id=1, user_id=1, title="PR", status=PRStatus.OPEN)
    db.add(pr)
    db.commit()

    review_payload = {
        "action": "submitted",
        "repository": {"name": "hacktoberfest-web"},
        "pull_request": {"id": 9991, "number": 42},
        "review": {
            "state": "changes_requested",
            "body": "Please add transition animation to toggle button.",
            "user": {"login": "aditya-maint"}
        }
    }

    res = client.post(
        "/webhooks/github",
        json=review_payload,
        headers={"X-GitHub-Event": "pull_request_review"}
    )
    assert res.status_code == 200

    # Verify Review was saved
    rev = db.query(Review).filter(Review.pr_id == pr.id).first()
    assert rev is not None
    assert rev.status == ReviewStatus.CHANGES_REQUESTED
    assert rev.reviewer_id == 2

    # Verify Contribution status updated to changes_requested
    contrib = db.query(Contribution).filter(Contribution.issue_id == 1).first()
    assert contrib.status == ContributionStatus.CHANGES_REQUESTED

    # Verify Notification sent to student
    notif = db.query(Notification).filter(Notification.user_id == 1).first()
    assert notif is not None
    assert notif.type == "pr_review"


def test_pull_request_merged_completion(client_and_db, monkeypatch):
    client, db = client_and_db
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")

    pr = PullRequest(id=1, repo_id=1, github_pr_id=9991, issue_id=1, user_id=1, title="PR", status=PRStatus.OPEN)
    db.add(pr)
    db.commit()

    merged_payload = {
        "action": "closed",
        "repository": {"name": "hacktoberfest-web"},
        "pull_request": {
            "id": 9991,
            "number": 42,
            "title": "feat: dark mode switcher",
            "merged": True,
            "user": {"login": "aarav-sharma"}
        }
    }

    res = client.post(
        "/webhooks/github",
        json=merged_payload,
        headers={"X-GitHub-Event": "pull_request"}
    )
    assert res.status_code == 200

    # PR marked MERGED
    db_pr = db.query(PullRequest).filter(PullRequest.id == 1).first()
    assert db_pr.status == PRStatus.MERGED

    # Issue closed
    issue = db.query(Issue).filter(Issue.id == 1).first()
    assert issue.status == IssueStatus.CLOSED

    # Claim completed
    claim = db.query(Claim).filter(Claim.id == 1).first()
    assert claim.status == ClaimStatus.COMPLETED

    # Contribution marked MERGED and VALID
    contrib = db.query(Contribution).filter(Contribution.issue_id == 1).first()
    assert contrib.status == ContributionStatus.MERGED
    assert contrib.validation_status == ContributionValidation.VALID

    # Celebration notification
    merged_notif = db.query(Notification).filter(Notification.user_id == 1, Notification.type == "pr_merged").first()
    assert merged_notif is not None


def test_push_event_records_commits(client_and_db, monkeypatch):
    client, db = client_and_db
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")

    push_payload = {
        "repository": {"name": "hacktoberfest-web"},
        "sender": {"login": "aarav-sharma"},
        "commits": [
            {
                "id": "commit_sha_1234567890",
                "message": "feat: initial commit for dark mode",
                "author": {"username": "aarav-sharma", "email": "aarav@psit.ac.in"}
            }
        ]
    }

    res = client.post(
        "/webhooks/github",
        json=push_payload,
        headers={"X-GitHub-Event": "push"}
    )
    assert res.status_code == 200

    # Verify commit saved and auto-linked to student's active claim
    c = db.query(Commit).filter(Commit.github_commit_sha == "commit_sha_1234567890").first()
    assert c is not None
    assert c.user_id == 1
    assert c.issue_id == 1
    assert c.message == "feat: initial commit for dark mode"


def test_repository_webhook_creation_and_deletion(client_and_db, monkeypatch):
    client, db = client_and_db
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")

    # 1. 'created' repository event
    created_payload = {
        "action": "created",
        "repository": {
            "name": "hacktoberfest-ios",
            "html_url": "https://github.com/gdgoc-psit/hacktoberfest-ios"
        }
    }
    res = client.post("/webhooks/github", json=created_payload, headers={"X-GitHub-Event": "repository"})
    assert res.status_code == 200
    repo = db.query(Repository).filter(Repository.name == "hacktoberfest-ios").first()
    assert repo is not None
    assert repo.github_repo_url == "https://github.com/gdgoc-psit/hacktoberfest-ios"

    # 2. 'deleted' repository event
    deleted_payload = {
        "action": "deleted",
        "repository": {
            "name": "hacktoberfest-ios",
            "html_url": "https://github.com/gdgoc-psit/hacktoberfest-ios"
        }
    }
    res = client.post("/webhooks/github", json=deleted_payload, headers={"X-GitHub-Event": "repository"})
    assert res.status_code == 200
    repo_after = db.query(Repository).filter(Repository.name == "hacktoberfest-ios").first()
    assert repo_after is None


def test_issues_webhook_auto_creates_repo_and_handles_deletion(client_and_db, monkeypatch):
    client, db = client_and_db
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", "")

    # Issue opened on an un-registered repository
    issue_payload = {
        "action": "opened",
        "repository": {
            "name": "hacktoberfest-cli",
            "html_url": "https://github.com/gdgoc-psit/hacktoberfest-cli"
        },
        "issue": {
            "id": 998877,
            "title": "Fix CLI spinner animation",
            "body": "Spinner freezes when downloading dependencies.",
            "labels": [{"name": "medium"}, {"name": "python"}]
        }
    }
    res = client.post("/webhooks/github", json=issue_payload, headers={"X-GitHub-Event": "issues"})
    assert res.status_code == 200

    # Verify repository was auto-created
    auto_repo = db.query(Repository).filter(Repository.name == "hacktoberfest-cli").first()
    assert auto_repo is not None

    # Verify issue was created under auto-created repository
    created_issue = db.query(Issue).filter(Issue.github_issue_id == 998877).first()
    assert created_issue is not None
    assert created_issue.title == "Fix CLI spinner animation"
    assert created_issue.repo_id == auto_repo.id

    # Issue deleted on GitHub
    delete_issue_payload = {
        "action": "deleted",
        "repository": {
            "name": "hacktoberfest-cli",
            "html_url": "https://github.com/gdgoc-psit/hacktoberfest-cli"
        },
        "issue": {
            "id": 998877
        }
    }
    res = client.post("/webhooks/github", json=delete_issue_payload, headers={"X-GitHub-Event": "issues"})
    assert res.status_code == 200

    deleted_issue = db.query(Issue).filter(Issue.github_issue_id == 998877).first()
    assert deleted_issue is None

