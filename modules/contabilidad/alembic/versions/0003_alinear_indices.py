"""Alinea los índices y la nulabilidad con los modelos (así `alembic check` queda limpio).

Sólo cambia nombres de índices y NOT NULL en dos columnas JSON: no toca datos.

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

RENOMBRES = [
    ("ix_lineas_asiento", "ix_asientos_lineas_asiento_id"),
    ("ix_lineas_cuenta", "ix_asientos_lineas_cuenta_codigo"),
    ("ix_comprobantes_asiento_id", "ix_comprobantes_iva_asiento_id"),
    ("ix_comprobantes_fecha", "ix_comprobantes_iva_fecha"),
    ("ix_comprobantes_libro", "ix_comprobantes_iva_libro"),
    ("ix_comprobantes_transaccion_id", "ix_comprobantes_iva_transaccion_id"),
    ("ix_definiciones_modulo", "ix_definiciones_asiento_modulo"),
    ("ix_definiciones_tipo", "ix_definiciones_asiento_tipo"),
    ("ix_extracto_asiento_linea_id", "ix_extracto_bancario_asiento_linea_id"),
    ("ix_extracto_cuenta_codigo", "ix_extracto_bancario_cuenta_codigo"),
    ("ix_extracto_fecha", "ix_extracto_bancario_fecha"),
]


def upgrade():
    for viejo, nuevo in RENOMBRES:
        op.execute(f'ALTER INDEX IF EXISTS "{viejo}" RENAME TO "{nuevo}"')
    # El código único de centros y diarios se expresa como índice único (como lo declara el modelo).
    op.execute("ALTER TABLE centros_costo DROP CONSTRAINT IF EXISTS centros_costo_codigo_key")
    op.execute("ALTER TABLE diarios DROP CONSTRAINT IF EXISTS diarios_codigo_key")
    op.create_index("ix_centros_costo_codigo", "centros_costo", ["codigo"], unique=True)
    op.create_index("ix_diarios_codigo", "diarios", ["codigo"], unique=True)
    # Las líneas de una definición y los datos de una transacción siempre están (aunque sean {}).
    op.execute("UPDATE definiciones_asiento SET lineas = '[]'::jsonb WHERE lineas IS NULL")
    op.execute("UPDATE transacciones SET datos = '{}'::jsonb WHERE datos IS NULL")
    op.alter_column("definiciones_asiento", "lineas", nullable=False)
    op.alter_column("transacciones", "datos", nullable=False)


def downgrade():
    op.alter_column("transacciones", "datos", nullable=True)
    op.alter_column("definiciones_asiento", "lineas", nullable=True)
    op.drop_index("ix_diarios_codigo", table_name="diarios")
    op.drop_index("ix_centros_costo_codigo", table_name="centros_costo")
    op.create_unique_constraint("diarios_codigo_key", "diarios", ["codigo"])
    op.create_unique_constraint("centros_costo_codigo_key", "centros_costo", ["codigo"])
    for viejo, nuevo in RENOMBRES:
        op.execute(f'ALTER INDEX IF EXISTS "{nuevo}" RENAME TO "{viejo}"')
