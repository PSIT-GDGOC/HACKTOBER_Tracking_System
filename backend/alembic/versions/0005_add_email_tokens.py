"""add is_email_verified and email_tokens table

Revision ID: 0005_add_email_tokens
Revises: 0004_bigint_github_ids
Create Date: 2026-09-29 21:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = "0005_add_email_tokens"
down_revision: Union[str, Sequence[str], None] = "0004_bigint_github_ids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = Inspector.from_engine(conn)

    # 1. Add is_email_verified column to users if missing
    user_cols = [c["name"] for c in insp.get_columns("users")]
    if "is_email_verified" not in user_cols:
        op.add_column(
            "users",
            sa.Column("is_email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false"))
        )

    # 2. Create email_tokens table if not exists
    tables = insp.get_table_names()
    if "email_tokens" not in tables:
        op.create_table(
            "email_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("purpose", sa.String(length=50), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_email_tokens_id", "email_tokens", ["id"])
        op.create_index("ix_email_tokens_user_id", "email_tokens", ["user_id"])
        op.create_index("ix_email_tokens_token_hash", "email_tokens", ["token_hash"])
        op.create_index("ix_email_tokens_purpose", "email_tokens", ["purpose"])


def downgrade() -> None:
    conn = op.get_bind()
    insp = Inspector.from_engine(conn)
    tables = insp.get_table_names()

    if "email_tokens" in tables:
        op.drop_index("ix_email_tokens_purpose", table_name="email_tokens")
        op.drop_index("ix_email_tokens_token_hash", table_name="email_tokens")
        op.drop_index("ix_email_tokens_user_id", table_name="email_tokens")
        op.drop_index("ix_email_tokens_id", table_name="email_tokens")
        op.drop_table("email_tokens")

    user_cols = [c["name"] for c in insp.get_columns("users")]
    if "is_email_verified" in user_cols:
        op.drop_column("users", "is_email_verified")
