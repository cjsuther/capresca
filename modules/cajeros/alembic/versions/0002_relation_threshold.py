"""add amount_threshold and currency to authorization_relations

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "authorization_relations",
        sa.Column("amount_threshold", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "authorization_relations",
        sa.Column("currency", sa.String(10), nullable=False, server_default="ARS"),
    )


def downgrade() -> None:
    op.drop_column("authorization_relations", "currency")
    op.drop_column("authorization_relations", "amount_threshold")
