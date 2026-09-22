"""Esquema inicial: lotes, pagos, aprobaciones y bitácora.

Revision ID: 0001
Revises:
Create Date: 2026-09-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("origen", sa.String(20), nullable=False),
        sa.Column("referencia_origen", sa.String(80), nullable=False),
        sa.Column("descripcion", sa.String(200), nullable=False),
        sa.Column("callback_url", sa.String(300), nullable=True),
        sa.Column("estado", sa.String(25), nullable=False),
        sa.Column("motivo_rechazo", sa.String(300), nullable=False),
        sa.Column("simulado", sa.Boolean(), nullable=False),
        sa.Column("creado_por", sa.String(60), nullable=False),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("aprobado_en", sa.DateTime(), nullable=True),
        sa.Column("enviado_por", sa.String(60), nullable=False),
        sa.Column("enviado_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("origen", "referencia_origen", name="uq_lote_origen_referencia"),
    )
    op.create_index("ix_lotes_codigo", "lotes", ["codigo"], unique=True)
    op.create_index("ix_lotes_origen", "lotes", ["origen"])
    op.create_index("ix_lotes_estado", "lotes", ["estado"])

    op.create_table(
        "pagos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote_id", sa.Integer(), sa.ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referencia_externa", sa.String(80), nullable=False),
        sa.Column("beneficiario", sa.String(160), nullable=False),
        sa.Column("documento", sa.String(20), nullable=False),
        sa.Column("cbu", sa.String(22), nullable=False),
        sa.Column("monto", sa.Numeric(16, 2), nullable=False),
        sa.Column("concepto", sa.String(120), nullable=False),
        sa.Column("estado", sa.String(15), nullable=False),
        sa.Column("motivo", sa.String(300), nullable=False),
        sa.Column("transfer_id", sa.Integer(), nullable=True),
        sa.Column("id_operacion_ib", sa.String(80), nullable=False),
        sa.Column("estado_banco", sa.String(40), nullable=False),
        sa.Column("enviado_en", sa.DateTime(), nullable=True),
        sa.Column("confirmado_en", sa.DateTime(), nullable=True),
        sa.Column("notificado", sa.String(15), nullable=False),
    )
    op.create_index("ix_pagos_lote_id", "pagos", ["lote_id"])
    op.create_index("ix_pagos_referencia_externa", "pagos", ["referencia_externa"])
    op.create_index("ix_pagos_estado", "pagos", ["estado"])

    op.create_table(
        "lote_aprobaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote_id", sa.Integer(), sa.ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nivel_orden", sa.Integer(), nullable=False),
        sa.Column("aprobado_por", sa.String(60), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lote_id", "nivel_orden", name="uq_lote_aprobacion_nivel"),
    )
    op.create_index("ix_lote_aprobaciones_lote_id", "lote_aprobaciones", ["lote_id"])

    op.create_table(
        "lote_eventos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote_id", sa.Integer(), sa.ForeignKey("lotes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario", sa.String(60), nullable=False),
        sa.Column("accion", sa.String(40), nullable=False),
        sa.Column("detalle", sa.Text(), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_lote_eventos_lote_id", "lote_eventos", ["lote_id"])


def downgrade() -> None:
    for t in ("lote_eventos", "lote_aprobaciones", "pagos", "lotes"):
        op.drop_table(t)
