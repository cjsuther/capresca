"""Outbox de transacciones para Contabilidad: se graban con el pago y se reenvían hasta que llegan.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outbox_contable",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("accion", sa.String(10), nullable=False, server_default="REGISTRAR"),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("referencia", sa.String(80), nullable=False),
        sa.Column("asiento_id", sa.Integer, nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("estado", sa.String(10), nullable=False, server_default="PENDIENTE"),
        sa.Column("intentos", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ultimo_error", sa.String(300), nullable=False, server_default=""),
        sa.Column("proximo_intento", sa.DateTime, nullable=False),
        sa.Column("creado_en", sa.DateTime, nullable=False),
        sa.Column("enviado_en", sa.DateTime, nullable=True),
    )
    op.create_index("ix_outbox_contable_tipo", "outbox_contable", ["tipo"])
    op.create_index("ix_outbox_contable_referencia", "outbox_contable", ["referencia"])
    op.create_index("ix_outbox_contable_estado", "outbox_contable", ["estado"])


def downgrade():
    op.drop_table("outbox_contable")
