"""add currency column to transfers

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "transfers",
        sa.Column("moneda", sa.String(3), nullable=False, server_default="ARS"),
    )


def downgrade() -> None:
    op.drop_column("transfers", "moneda")
