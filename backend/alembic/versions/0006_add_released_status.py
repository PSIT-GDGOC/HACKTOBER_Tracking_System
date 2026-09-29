"""add released to contributionstatus enum

Revision ID: 0006_add_released_status
Revises: 0005_add_email_tokens
Create Date: 2026-09-30 01:27:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_add_released_status"
down_revision: Union[str, Sequence[str], None] = "0005_add_email_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # Add 'released' to the PostgreSQL enum type if not already present
        op.execute(sa.text("ALTER TYPE contributionstatus ADD VALUE IF NOT EXISTS 'released';"))
        # Deduplicate any historical duplicate (user_id, issue_id) rows before adding unique index
        op.execute(sa.text(
            "DELETE FROM contributions a USING contributions b "
            "WHERE a.id < b.id AND a.user_id = b.user_id AND a.issue_id = b.issue_id;"
        ))
        # Enforce one contribution per (user, issue) pair to prevent duplicates
        op.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_contributions_user_issue "
            "ON contributions (user_id, issue_id);"
        ))


def downgrade() -> None:
    # Postgres enum values cannot be easily removed without recreating the enum,
    # which is unsafe in production without data migration.
    pass
