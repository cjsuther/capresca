"""Usuario de la plataforma que cargó la transferencia.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transfers", sa.Column("cargado_por", sa.String(60), nullable=True))


def downgrade() -> None:
    op.drop_column("transfers", "cargado_por")
