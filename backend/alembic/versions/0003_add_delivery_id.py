"""add delivery_id to webhook_jobs if missing

Revision ID: 0003_add_delivery_id
Revises: 0002_v2_schema_updates
Create Date: 2026-09-27 21:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = "0003_add_delivery_id"
down_revision: Union[str, Sequence[str], None] = "0002_v2_schema_updates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = Inspector.from_engine(conn)
    cols = [c["name"] for c in insp.get_columns("webhook_jobs")]

    if "delivery_id" not in cols:
        op.add_column("webhook_jobs", sa.Column("delivery_id", sa.String(length=100), nullable=True))
        op.create_index("ix_webhook_jobs_delivery_id", "webhook_jobs", ["delivery_id"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    insp = Inspector.from_engine(conn)
    cols = [c["name"] for c in insp.get_columns("webhook_jobs")]

    if "delivery_id" in cols:
        op.drop_index("ix_webhook_jobs_delivery_id", table_name="webhook_jobs")
        op.drop_column("webhook_jobs", "delivery_id")
