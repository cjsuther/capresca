"""add app_secret to whatsapp_config

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_config",
        sa.Column("app_secret", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("whatsapp_config", "app_secret")
