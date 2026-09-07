"""add reconciliation_adjustments table

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_adjustments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("reconciliation_record_id", sa.BigInteger(),
                  sa.ForeignKey("reconciliation_records.id"), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_by_username", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reconciliation_adjustments_record", "reconciliation_adjustments",
                    ["reconciliation_record_id"])


def downgrade() -> None:
    op.drop_index("ix_reconciliation_adjustments_record", table_name="reconciliation_adjustments")
    op.drop_table("reconciliation_adjustments")
