"""alter github_issue_id and github_pr_id to BigInteger

Revision ID: 0004_bigint_github_ids
Revises: 0003_add_delivery_id
Create Date: 2026-09-28 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_bigint_github_ids"
down_revision: Union[str, Sequence[str], None] = "0003_add_delivery_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Safely alter github_issue_id to BigInteger
    op.alter_column(
        "issues",
        "github_issue_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )
    # Safely alter github_pr_id to BigInteger
    op.alter_column(
        "pull_requests",
        "github_pr_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "pull_requests",
        "github_pr_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "issues",
        "github_issue_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
