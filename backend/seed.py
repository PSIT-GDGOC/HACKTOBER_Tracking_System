"""Seed script for local development and testing.

Populates the database with realistic test data across all 10 tables:
- 3 Users (Student, Maintainer, Admin)
- 2 Repositories (Web App, Android App)
- Sample Issues with various difficulties and tags
- Claims, Pull Requests, Commits, Contributions, Reviews, Notifications, and Activity Feed.
"""

from datetime import datetime, timezone
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from sqlalchemy.exc import OperationalError
from app.db import SessionLocal, engine, Base
from app.models import (
    User, UserRole, VerificationMethod,
    Repository, PlatformType,
    Issue, IssueDifficulty, IssueStatus,
    Claim, ClaimStatus,
    PullRequest, PRStatus,
    Commit,
    Contribution, ContributionStatus, ContributionValidation,
    Review, ReviewStatus,
    Notification,
    ActivityFeed,
    WebhookJob, WebhookJobStatus
)


def seed_database():
    print("🌱 Connecting to database to seed initial data...")
    try:
        # Create tables if not existing
        Base.metadata.create_all(bind=engine)
    except OperationalError as e:
        print(f"\n❌ Could not connect to the database: {e}")
        print("\n💡 Please ensure PostgreSQL is running or set your live DATABASE_URL (e.g. Neon or Supabase) in .env")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).first():
            print("⚠️ Database already has data. Skipping seed.")
            return

        print("Creating users...")
        student = User(
            name="Aarav Sharma",
            email="aarav.2200320100001@psit.ac.in",
            psit_roll_no="2200320100001",
            id_card_image_url="private/id_cards/aarav_2200320100001.png",
            qr_token="psit://verify/student/2200320100001/token_abc123",
            portal_snapshot_json={
                "name": "Aarav Sharma",
                "roll_no": "2200320100001",
                "department": "CSE",
                "status": "active"
            },
            verification_method=VerificationMethod.QR_AUTO,
            verified=True,
            verified_at=datetime.now(timezone.utc),
            github_username="aarav-sharma-psit",
            github_id="gh_123456",
            role=UserRole.STUDENT,
        )
        maintainer = User(
            name="Aditya Verma",
            email="aditya.verma@psit.ac.in",
            psit_roll_no="2100320100002",
            verification_method=VerificationMethod.MANUAL,
            verified=True,
            verified_at=datetime.now(timezone.utc),
            github_username="aditya-verma-lead",
            github_id="gh_234567",
            role=UserRole.MAINTAINER,
        )
        admin = User(
            name="Abu Ansari",
            email="abu.ansari@psit.ac.in",
            psit_roll_no="2100320100003",
            verification_method=VerificationMethod.MANUAL,
            verified=True,
            verified_at=datetime.now(timezone.utc),
            github_username="abu-ansari",
            github_id="gh_345678",
            role=UserRole.ADMIN,
        )
        db.add_all([student, maintainer, admin])
        db.flush()

        print("Creating repositories...")
        web_repo = Repository(
            name="gdgoc-hacktoberfest-web",
            github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-web",
            platform=PlatformType.WEB,
        )
        android_repo = Repository(
            name="gdgoc-hacktoberfest-android",
            github_repo_url="https://github.com/gdgoc-psit/hacktoberfest-android",
            platform=PlatformType.ANDROID,
        )
        db.add_all([web_repo, android_repo])
        db.flush()

        print("Creating issues...")
        issue1 = Issue(
            repo_id=web_repo.id,
            github_issue_id=101,
            title="Implement responsive navbar with dark mode toggle",
            description="Add a mobile drawer and clean dark mode switcher using Tailwind CSS.",
            difficulty=IssueDifficulty.EASY,
            category="frontend",
            tech_tags=["React", "TailwindCSS", "TypeScript"],
            labels=["good first issue", "ui/ux"],
            status=IssueStatus.CLAIMED,
        )
        issue2 = Issue(
            repo_id=android_repo.id,
            github_issue_id=201,
            title="Add biometric authentication flow with Jetpack Compose",
            description="Integrate AndroidX Biometric prompt for student login verification.",
            difficulty=IssueDifficulty.MEDIUM,
            category="security",
            tech_tags=["Kotlin", "Jetpack Compose", "Biometrics"],
            labels=["feature", "android"],
            status=IssueStatus.OPEN,
        )
        issue3 = Issue(
            repo_id=web_repo.id,
            github_issue_id=102,
            title="Optimize leaderboard query indexing and pagination",
            description="Refactor leaderboard query to use window functions and cursor pagination.",
            difficulty=IssueDifficulty.HARD,
            category="backend",
            tech_tags=["PostgreSQL", "SQLAlchemy", "FastAPI"],
            labels=["enhancement", "performance"],
            status=IssueStatus.OPEN,
        )
        db.add_all([issue1, issue2, issue3])
        db.flush()

        print("Creating claim for student...")
        claim = Claim(
            issue_id=issue1.id,
            user_id=student.id,
            status=ClaimStatus.ACTIVE,
        )
        db.add(claim)
        db.flush()

        print("Creating pull request & commit...")
        pr = PullRequest(
            repo_id=web_repo.id,
            github_pr_id=301,
            issue_id=issue1.id,
            user_id=student.id,
            title="feat(navbar): add responsive navigation and dark mode toggle",
            status=PRStatus.OPEN,
            reviewer_id=maintainer.id,
        )
        db.add(pr)
        db.flush()

        commit = Commit(
            repo_id=web_repo.id,
            github_commit_sha="a1b2c3d4e5f67890123456789abcdef012345678",
            user_id=student.id,
            message="feat: complete responsive navbar with dark mode switcher",
            issue_id=issue1.id,
            pr_id=pr.id,
        )
        db.add(commit)
        db.flush()

        print("Creating contribution record...")
        contribution = Contribution(
            user_id=student.id,
            issue_id=issue1.id,
            pr_id=pr.id,
            status=ContributionStatus.UNDER_REVIEW,
            validation_status=ContributionValidation.PENDING,
            timeline_json=[
                {
                    "status": "claimed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": "Claimed issue #101",
                },
                {
                    "status": "in_progress",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": "Started working on branch feat/navbar",
                },
                {
                    "status": "pr_submitted",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": "Submitted PR #301",
                },
                {
                    "status": "under_review",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "detail": "Assigned maintainer for review",
                },
            ],
        )
        db.add(contribution)
        db.flush()

        print("Creating review...")
        review = Review(
            pr_id=pr.id,
            reviewer_id=maintainer.id,
            status=ReviewStatus.COMMENTED,
            comment="Looks great overall! Please check the mobile view transition duration.",
        )
        db.add(review)

        print("Creating notification & activity feed...")
        notification = Notification(
            user_id=student.id,
            type="pr_review",
            payload={
                "title": "New review on your PR",
                "message": "Maintainer commented on PR #301: 'Looks great overall...'",
                "pr_id": pr.id,
            },
            read=False,
        )
        db.add(notification)

        activity = ActivityFeed(
            type="claim_created",
            actor_id=student.id,
            target_type="issue",
            target_id=issue1.id,
        )
        db.add(activity)

        print("Creating sample webhook job (Table #11)...")
        webhook_job = WebhookJob(
            event_type="issues",
            payload_json={
                "action": "opened",
                "issue": {
                    "number": 101,
                    "title": "Fix navbar responsive collapse on mobile"
                }
            },
            status=WebhookJobStatus.DONE,
            attempts=1,
            next_attempt_at=datetime.now(timezone.utc),
        )
        db.add(webhook_job)

        db.commit()
        print("✅ Database successfully seeded with test data!")
    except Exception as e:
        db.rollback()
        print(f"❌ Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
