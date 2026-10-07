"""Órdenes de pago de créditos: resoluciones / disposiciones con sus lotes, pagadas por un lote de pagos.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ordenes_pago",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("anio", sa.Integer, nullable=False),
        sa.Column("numero", sa.Integer, nullable=False),
        sa.Column("estado", sa.String(15), nullable=False, server_default="CONFECCIONADA"),
        sa.Column("actos", sa.JSON, nullable=False),
        sa.Column("importe", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("cantidad", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lote_id", sa.Integer, sa.ForeignKey("lotes.id"), nullable=True, unique=True),
        sa.Column("creado_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("creado_en", sa.DateTime, server_default=sa.func.now()),
        sa.Column("anulada_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("anulada_en", sa.DateTime, nullable=True),
        sa.Column("motivo_anulacion", sa.String(300), nullable=False, server_default=""),
        sa.UniqueConstraint("anio", "numero", name="uq_orden_pago_anio_numero"),
    )
    op.create_index("ix_ordenes_pago_estado", "ordenes_pago", ["estado"])


def downgrade():
    op.drop_index("ix_ordenes_pago_estado", table_name="ordenes_pago")
    op.drop_table("ordenes_pago")
