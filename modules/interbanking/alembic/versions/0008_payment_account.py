"""add outbound payment account fields to credentials

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interbanking_credentials",
                  sa.Column("payment_account_number", sa.String(50), nullable=True))
    op.add_column("interbanking_credentials",
                  sa.Column("payment_account_type", sa.String(5), nullable=True))
    op.add_column("interbanking_credentials",
                  sa.Column("payment_bank_number", sa.String(5), nullable=True))
    op.add_column("interbanking_credentials",
                  sa.Column("payment_currency", sa.String(5), nullable=True))


def downgrade() -> None:
    op.drop_column("interbanking_credentials", "payment_currency")
    op.drop_column("interbanking_credentials", "payment_bank_number")
    op.drop_column("interbanking_credentials", "payment_account_type")
    op.drop_column("interbanking_credentials", "payment_account_number")
