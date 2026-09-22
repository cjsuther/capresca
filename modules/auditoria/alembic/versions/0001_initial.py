"""Registro de auditoría: un evento por acción sobre la información del sistema.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eventos",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("usuario", sa.String(60), nullable=False, server_default=""),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("ip", sa.String(64), nullable=False, server_default=""),
        sa.Column("modulo", sa.String(30), nullable=False, server_default=""),
        sa.Column("operacion", sa.String(15), nullable=False, server_default="ACCION"),
        sa.Column("entidad", sa.String(60), nullable=False, server_default=""),
        sa.Column("entidad_id", sa.String(80), nullable=False, server_default=""),
        sa.Column("descripcion", sa.String(300), nullable=False, server_default=""),
        sa.Column("metodo", sa.String(8), nullable=False, server_default=""),
        sa.Column("ruta", sa.String(300), nullable=False, server_default=""),
        sa.Column("estado_http", sa.Integer(), nullable=True),
        sa.Column("exito", sa.Boolean(), nullable=True),
        sa.Column("origen", sa.String(10), nullable=False, server_default="MODULO"),
        sa.Column("request_id", sa.String(40), nullable=False, server_default=""),
        sa.Column("cambios", postgresql.JSONB(), nullable=True),
        sa.Column("detalle", sa.Text(), nullable=False, server_default=""),
    )
    for col in ("fecha", "usuario", "modulo", "operacion", "entidad", "entidad_id", "origen", "request_id"):
        op.create_index(f"ix_eventos_{col}", "eventos", [col])
    # La consulta típica es "todo lo que le pasó a este registro".
    op.create_index("ix_eventos_registro", "eventos", ["modulo", "entidad", "entidad_id"])


def downgrade():
    op.drop_table("eventos")
