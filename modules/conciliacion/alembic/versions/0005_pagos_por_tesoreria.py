"""Pagos a agencias por Tesorería: lote en el que viaja cada pago.

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reconciliation_payments", sa.Column("tesoreria_lote", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("reconciliation_payments", "tesoreria_lote")
