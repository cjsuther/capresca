"""add is_payment_account flag to client_cbus

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
    op.add_column(
        "client_cbus",
        sa.Column("is_payment_account", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("client_cbus", "is_payment_account")
