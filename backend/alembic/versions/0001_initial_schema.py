"""Initial schema for 10 tables

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-22 11:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("psit_roll_no", sa.String(length=50), nullable=False),
        sa.Column("erp_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("github_username", sa.String(length=100), nullable=True),
        sa.Column("github_id", sa.String(length=100), nullable=True),
        sa.Column(
            "role",
            sa.Enum("student", "maintainer", "admin", name="userrole"),
            nullable=False,
            server_default="student",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_psit_roll_no", "users", ["psit_roll_no"], unique=True)
    op.create_index("ix_users_github_username", "users", ["github_username"], unique=True)
    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)

    # 2. Repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("github_repo_url", sa.String(length=500), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("web", "android", name="platformtype"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_repositories_id", "repositories", ["id"])
    op.create_index("ix_repositories_name", "repositories", ["name"], unique=True)
    op.create_index("ix_repositories_github_repo_url", "repositories", ["github_repo_url"], unique=True)

    # 3. Issues table
    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_issue_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "difficulty",
            sa.Enum("easy", "medium", "hard", name="issuedifficulty"),
            nullable=False,
            server_default="easy",
        ),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("tech_tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("labels", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "status",
            sa.Enum("open", "claimed", "in_progress", "closed", name="issuestatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_issues_id", "issues", ["id"])
    op.create_index("ix_issues_repo_id", "issues", ["repo_id"])
    op.create_index("ix_issues_github_issue_id", "issues", ["github_issue_id"], unique=True)
    op.create_index("ix_issues_status", "issues", ["status"])
    op.create_index("ix_issues_repo_status", "issues", ["repo_id", "status"])

    # 4. Claims table
    op.create_table(
        "claims",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "status",
            sa.Enum("active", "released", "expired", "completed", name="claimstatus"),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_index("ix_claims_id", "claims", ["id"])
    op.create_index("ix_claims_issue_id", "claims", ["issue_id"])
    op.create_index("ix_claims_user_id", "claims", ["user_id"])
    op.create_index("ix_claims_status", "claims", ["status"])
    # Partial unique index: only one active claim per issue
    op.create_index(
        "uq_active_claim_per_issue",
        "claims",
        ["issue_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    # 5. Pull Requests table
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_pr_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "merged", "closed", "draft", name="prstatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_pull_requests_id", "pull_requests", ["id"])
    op.create_index("ix_pull_requests_repo_id", "pull_requests", ["repo_id"])
    op.create_index("ix_pull_requests_github_pr_id", "pull_requests", ["github_pr_id"], unique=True)
    op.create_index("ix_pull_requests_issue_id", "pull_requests", ["issue_id"])
    op.create_index("ix_pull_requests_user_id", "pull_requests", ["user_id"])
    op.create_index("ix_pull_requests_status", "pull_requests", ["status"])
    op.create_index("ix_pull_requests_reviewer_id", "pull_requests", ["reviewer_id"])
    op.create_index("ix_pr_repo_status", "pull_requests", ["repo_id", "status"])

    # 6. Commits table
    op.create_table(
        "commits",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("github_commit_sha", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pr_id", sa.Integer(), sa.ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("committed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_commits_id", "commits", ["id"])
    op.create_index("ix_commits_repo_id", "commits", ["repo_id"])
    op.create_index("ix_commits_github_commit_sha", "commits", ["github_commit_sha"], unique=True)
    op.create_index("ix_commits_user_id", "commits", ["user_id"])
    op.create_index("ix_commits_issue_id", "commits", ["issue_id"])
    op.create_index("ix_commits_pr_id", "commits", ["pr_id"])
    op.create_index("ix_commits_repo_user", "commits", ["repo_id", "user_id"])

    # 7. Contributions table
    op.create_table(
        "contributions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pr_id", sa.Integer(), sa.ForeignKey("pull_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "claimed",
                "in_progress",
                "pr_submitted",
                "under_review",
                "changes_requested",
                "accepted",
                "merged",
                name="contributionstatus",
            ),
            nullable=False,
            server_default="claimed",
        ),
        sa.Column(
            "validation_status",
            sa.Enum("valid", "pending", "rejected", "duplicate", "invalid", name="contributionvalidation"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("timeline_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contributions_id", "contributions", ["id"])
    op.create_index("ix_contributions_user_id", "contributions", ["user_id"])
    op.create_index("ix_contributions_issue_id", "contributions", ["issue_id"])
    op.create_index("ix_contributions_pr_id", "contributions", ["pr_id"])
    op.create_index("ix_contributions_status", "contributions", ["status"])
    op.create_index("ix_contributions_validation_status", "contributions", ["validation_status"])
    op.create_index("ix_contributions_user_status", "contributions", ["user_id", "status"])

    # 8. Reviews table
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("pr_id", sa.Integer(), sa.ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("approved", "changes_requested", "commented", "dismissed", name="reviewstatus"),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_reviews_id", "reviews", ["id"])
    op.create_index("ix_reviews_pr_id", "reviews", ["pr_id"])
    op.create_index("ix_reviews_reviewer_id", "reviews", ["reviewer_id"])
    op.create_index("ix_reviews_status", "reviews", ["status"])
    op.create_index("ix_reviews_pr_status", "reviews", ["pr_id", "status"])

    # 9. Notifications table
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_type", "notifications", ["type"])
    op.create_index("ix_notifications_read", "notifications", ["read"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "read"])

    # 10. Activity Feed table
    op.create_table(
        "activity_feed",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_activity_feed_id", "activity_feed", ["id"])
    op.create_index("ix_activity_feed_type", "activity_feed", ["type"])
    op.create_index("ix_activity_feed_actor_id", "activity_feed", ["actor_id"])
    op.create_index("ix_activity_feed_created_at", "activity_feed", ["created_at"])
    op.create_index("ix_activity_feed_type_created", "activity_feed", ["type", "created_at"])


def downgrade() -> None:
    op.drop_table("activity_feed")
    op.drop_table("notifications")
    op.drop_table("reviews")
    op.drop_table("contributions")
    op.drop_table("commits")
    op.drop_table("pull_requests")
    op.drop_table("claims")
    op.drop_table("issues")
    op.drop_table("repositories")
    op.drop_table("users")

    # Drop enums
    for enum_name in [
        "reviewstatus",
        "contributionvalidation",
        "contributionstatus",
        "prstatus",
        "claimstatus",
        "issuestatus",
        "issuedifficulty",
        "platformtype",
        "userrole",
    ]:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
