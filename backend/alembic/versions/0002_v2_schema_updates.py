"""v2 schema updates: ID/QR verification fields on users and webhook_jobs table

Revision ID: 0002_v2_schema_updates
Revises: 0001_initial_schema
Create Date: 2026-09-24 00:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0002_v2_schema_updates"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Create enum type FIRST
    verification_method_enum = postgresql.ENUM(
        "qr_auto", "manual",
        name="verification_method",
    )
    verification_method_enum.create(bind, checkfirst=True)

    # 2. Update users table with v2 verification fields and drop erp_verified
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("id_card_image_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("qr_token", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("portal_snapshot_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "verification_method",
                verification_method_enum,
                nullable=True,
            )
        )
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(), nullable=True))
        batch_op.drop_column("erp_verified")

    # 3. Create webhook_jobs table (Table #11 replacing Celery broker)
    op.create_table(
        "webhook_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False, server_default="unknown"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "done", "failed", name="webhookjobstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_jobs_id", "webhook_jobs", ["id"])
    op.create_index("ix_webhook_jobs_event_type", "webhook_jobs", ["event_type"])
    op.create_index("ix_webhook_jobs_status", "webhook_jobs", ["status"])
    op.create_index("ix_webhook_jobs_next_attempt_at", "webhook_jobs", ["next_attempt_at"])
    op.create_index(
        "ix_webhook_jobs_status_next_attempt",
        "webhook_jobs",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    # 1. Drop webhook_jobs table
    op.drop_index("ix_webhook_jobs_status_next_attempt", table_name="webhook_jobs")
    op.drop_index("ix_webhook_jobs_next_attempt_at", table_name="webhook_jobs")
    op.drop_index("ix_webhook_jobs_status", table_name="webhook_jobs")
    op.drop_index("ix_webhook_jobs_event_type", table_name="webhook_jobs")
    op.drop_index("ix_webhook_jobs_id", table_name="webhook_jobs")
    op.drop_table("webhook_jobs")

    # 2. Revert users table changes
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("erp_verified", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )
        batch_op.drop_column("verified_at")
        batch_op.drop_column("verification_method")
        batch_op.drop_column("portal_snapshot_json")
        batch_op.drop_column("qr_token")
        batch_op.drop_column("id_card_image_url")

    # 3. Drop enum types LAST
    postgresql.ENUM(name="verification_method").drop(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM(name="webhookjobstatus").drop(
        op.get_bind(), checkfirst=True
    )
