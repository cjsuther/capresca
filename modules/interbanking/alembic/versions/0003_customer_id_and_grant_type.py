"""add customer_id and grant_type fields to credentials

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-17 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interbanking_credentials",
        sa.Column("customer_id", sa.String(50), nullable=True),
    )
    op.add_column(
        "interbanking_credentials",
        sa.Column(
            "grant_type",
            sa.String(30),
            nullable=False,
            server_default="password",
        ),
    )


def downgrade() -> None:
    op.drop_column("interbanking_credentials", "grant_type")
    op.drop_column("interbanking_credentials", "customer_id")
