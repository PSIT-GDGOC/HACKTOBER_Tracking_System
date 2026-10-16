"""Add shared email request throttling.

Revision ID: 0007_email_rate_limits
Revises: 0006_add_released_status
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_email_rate_limits"
down_revision = "0006_add_released_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_rate_limits",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("timestamps", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.Float(), nullable=False),
    )
    op.create_index("ix_email_rate_limits_expires_at", "email_rate_limits", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_email_rate_limits_expires_at", table_name="email_rate_limits")
    op.drop_table("email_rate_limits")
