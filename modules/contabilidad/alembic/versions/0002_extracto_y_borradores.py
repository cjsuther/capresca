"""Conciliación bancaria (extracto) y asientos en borrador.

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "extracto_bancario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cuenta_codigo", sa.String(20), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("descripcion", sa.String(200), nullable=False, server_default=""),
        sa.Column("referencia", sa.String(80), nullable=False, server_default=""),
        sa.Column("importe", sa.Numeric(16, 2), nullable=False),
        sa.Column("asiento_linea_id", sa.Integer(), nullable=True),
        sa.Column("conciliada_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("conciliada_en", sa.DateTime(), nullable=True),
        sa.Column("creada_en", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    for col in ("cuenta_codigo", "fecha", "asiento_linea_id"):
        op.create_index(f"ix_extracto_{col}", "extracto_bancario", [col])


def downgrade():
    op.drop_table("extracto_bancario")
