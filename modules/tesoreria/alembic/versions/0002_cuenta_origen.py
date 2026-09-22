"""Cuenta desde la que sale el pago: la elige el tesorero al enviar el lote.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

COLUMNAS = [("cuenta_origen", 50), ("cuenta_origen_tipo", 5), ("cuenta_origen_banco", 5),
            ("cuenta_origen_nombre", 120)]


def upgrade():
    for nombre, largo in COLUMNAS:
        op.add_column("lotes", sa.Column(nombre, sa.String(largo), nullable=False, server_default=""))


def downgrade():
    for nombre, _ in COLUMNAS:
        op.drop_column("lotes", nombre)
