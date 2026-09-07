"""add consolidation account fields to credentials

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interbanking_credentials",
                  sa.Column("consolidation_account_number", sa.String(50), nullable=True))
    op.add_column("interbanking_credentials",
                  sa.Column("consolidation_account_type", sa.String(5), nullable=True))
    op.add_column("interbanking_credentials",
                  sa.Column("consolidation_bank_number", sa.String(5), nullable=True))
    op.add_column("interbanking_credentials",
                  sa.Column("consolidation_currency", sa.String(5), nullable=True))


def downgrade() -> None:
    op.drop_column("interbanking_credentials", "consolidation_currency")
    op.drop_column("interbanking_credentials", "consolidation_bank_number")
    op.drop_column("interbanking_credentials", "consolidation_account_type")
    op.drop_column("interbanking_credentials", "consolidation_account_number")
