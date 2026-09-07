"""add reconciliation_payments table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("reconciliation_record_id", sa.BigInteger(),
                  sa.ForeignKey("reconciliation_records.id"), nullable=False, unique=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("agency_number", sa.String(20), nullable=True),
        sa.Column("cbu_destino", sa.String(22), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRY_RUN"),
        sa.Column("ib_transfer_id", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_reconciliation_payments_record", "reconciliation_payments",
                    ["reconciliation_record_id"])


def downgrade() -> None:
    op.drop_index("ix_reconciliation_payments_record", table_name="reconciliation_payments")
    op.drop_table("reconciliation_payments")
