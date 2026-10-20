"""Quién envió (o reintentó) cada pago.

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pagos", sa.Column("enviado_por", sa.String(60), nullable=False, server_default=""))


def downgrade():
    op.drop_column("pagos", "enviado_por")
