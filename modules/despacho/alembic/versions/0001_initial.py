"""Esquema inicial de Despacho: modelos, resoluciones, anexo y expedientes.

Revision ID: 0001
Revises:
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "modelos_resolucion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("descripcion", sa.String(120), nullable=False, server_default=""),
        sa.Column("tipo", sa.String(3), nullable=False, server_default="RES"),
        sa.Column("es_seguros", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("plantilla", sa.Text(), nullable=False, server_default=""),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_modelos_resolucion_codigo", "modelos_resolucion", ["codigo"])

    op.create_table(
        "resoluciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(3), nullable=False, server_default="RES"),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("numero_real", sa.Integer(), nullable=True),
        sa.Column("fecha_real", sa.Date(), nullable=True),
        sa.Column("organo", sa.String(60), nullable=False, server_default=""),
        sa.Column("asunto", sa.String(200), nullable=False, server_default=""),
        sa.Column("motivo_codigo", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("motivo", sa.String(120), nullable=False, server_default=""),
        sa.Column("importe", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("modelo_id", sa.Integer(), sa.ForeignKey("modelos_resolucion.id"), nullable=True),
        sa.Column("origen", sa.String(40), nullable=False, server_default=""),
        sa.Column("nro_op", sa.Integer(), nullable=True),
        sa.Column("texto", sa.Text(), nullable=False, server_default=""),
        sa.Column("estado", sa.String(1), nullable=False, server_default="B"),
        sa.Column("anulada", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("motivo_anulacion", sa.String(200), nullable=False, server_default=""),
        sa.Column("creado_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # El correlativo es único por año y tipo: la DB es el árbitro, no un lock aplicativo.
        sa.UniqueConstraint("anio", "tipo", "numero", name="uq_resoluciones_anio_tipo_numero"),
    )
    for col in ("numero", "anio", "tipo", "numero_real", "estado"):
        op.create_index(f"ix_resoluciones_{col}", "resoluciones", [col])

    op.create_table(
        "resolucion_beneficiarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resolucion_id", sa.Integer(),
                  sa.ForeignKey("resoluciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo_doc", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("nro_doc", sa.String(11), nullable=False, server_default=""),
        sa.Column("nombre", sa.String(80), nullable=False, server_default=""),
        sa.Column("tipo_bene", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("importe", sa.Numeric(16, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_resolucion_beneficiarios_resolucion_id", "resolucion_beneficiarios",
                    ["resolucion_id"])
    op.create_index("ix_resolucion_beneficiarios_nro_doc", "resolucion_beneficiarios", ["nro_doc"])

    op.create_table(
        "solicitudes_anexo",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("fecha_solicitud", sa.Date(), nullable=True),
        sa.Column("cuil", sa.String(11), nullable=False, server_default=""),
        sa.Column("apellido_nombre", sa.String(80), nullable=False, server_default=""),
        sa.Column("dni", sa.String(9), nullable=False, server_default=""),
        sa.Column("monto", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("linea", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("linea_nombre", sa.String(80), nullable=False, server_default=""),
        sa.Column("cartera", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estado", sa.String(2), nullable=False, server_default=""),
        sa.Column("cubica", sa.String(2), nullable=False, server_default=""),
        sa.Column("lote", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("numero_resolucion", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fecha_resolucion", sa.Date(), nullable=True),
        sa.Column("en_resolucion", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for col in ("cuil", "apellido_nombre", "linea", "estado", "lote", "numero_resolucion",
                "en_resolucion"):
        op.create_index(f"ix_solicitudes_anexo_{col}", "solicitudes_anexo", [col])

    op.create_table(
        "expedientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.String(20), nullable=False, unique=True),
        sa.Column("caratula", sa.String(200), nullable=False),
        sa.Column("iniciador", sa.String(80), nullable=False, server_default=""),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(1), nullable=False, server_default="T"),
        sa.Column("oficina_actual", sa.String(60), nullable=False, server_default=""),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_expedientes_numero", "expedientes", ["numero"])
    op.create_index("ix_expedientes_estado", "expedientes", ["estado"])

    op.create_table(
        "pases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("expediente_id", sa.Integer(),
                  sa.ForeignKey("expedientes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("oficina_origen", sa.String(60), nullable=False, server_default=""),
        sa.Column("oficina_destino", sa.String(60), nullable=False, server_default=""),
        sa.Column("motivo", sa.String(200), nullable=False, server_default=""),
        sa.Column("usuario", sa.String(60), nullable=False, server_default=""),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pases_expediente_id", "pases", ["expediente_id"])

    op.create_table(
        "importaciones_despacho",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("archivo", sa.String(255), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estado", sa.String(15), nullable=False, server_default="PENDIENTE"),
        sa.Column("modelos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resoluciones", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("beneficiarios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("solicitudes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("omitidas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mensaje", sa.Text(), nullable=False, server_default=""),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("terminado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_importaciones_despacho_estado", "importaciones_despacho", ["estado"])


def downgrade() -> None:
    for t in ("importaciones_despacho", "pases", "expedientes", "solicitudes_anexo",
              "resolucion_beneficiarios", "resoluciones", "modelos_resolucion"):
        op.drop_table(t)
