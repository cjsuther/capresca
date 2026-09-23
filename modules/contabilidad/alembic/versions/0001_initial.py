"""Esquema inicial de Contabilidad: plan de cuentas, ejercicios, definiciones, transacciones y asientos.

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
        "empresas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("razon_social", sa.String(120), nullable=False),
        sa.Column("cuit", sa.String(11), nullable=False, server_default=""),
        sa.Column("condicion_iva", sa.String(30), nullable=False, server_default="RESPONSABLE_INSCRIPTO"),
        sa.Column("domicilio", sa.String(160), nullable=False, server_default=""),
        sa.Column("inicio_actividades", sa.Date(), nullable=True),
        sa.Column("predeterminada", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "cuentas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("rubro", sa.String(15), nullable=False),
        sa.Column("imputable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("saldo_normal", sa.String(10), nullable=False, server_default="DEUDOR"),
        sa.Column("moneda", sa.String(3), nullable=False, server_default="ARS"),
        sa.Column("ajustable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requiere_centro", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("descripcion", sa.String(300), nullable=False, server_default=""),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("codigo", name="uq_cuenta_codigo"),
    )
    op.create_index("ix_cuentas_codigo", "cuentas", ["codigo"])
    op.create_index("ix_cuentas_rubro", "cuentas", ["rubro"])
    op.create_table(
        "centros_costo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(12), nullable=False, unique=True),
        sa.Column("nombre", sa.String(80), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "diarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(12), nullable=False, unique=True),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "ejercicios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.Integer(), nullable=False, unique=True),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False, server_default="ABIERTO"),
        sa.Column("cerrado_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("cerrado_en", sa.DateTime(), nullable=True),
        sa.Column("cuenta_resultado", sa.String(20), nullable=False, server_default=""),
    )
    op.create_index("ix_ejercicios_estado", "ejercicios", ["estado"])
    op.create_table(
        "definiciones_asiento",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modulo", sa.String(30), nullable=False),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("diario_codigo", sa.String(12), nullable=False, server_default="VAR"),
        sa.Column("leyenda", sa.String(200), nullable=False, server_default=""),
        sa.Column("lineas", postgresql.JSONB(), nullable=True),
        sa.Column("vigente_desde", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creada_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("creada_en", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("modulo", "tipo", "vigente_desde", name="uq_definicion_vigencia"),
    )
    op.create_index("ix_definiciones_modulo", "definiciones_asiento", ["modulo"])
    op.create_index("ix_definiciones_tipo", "definiciones_asiento", ["tipo"])
    op.create_table(
        "asientos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ejercicio_id", sa.Integer(), sa.ForeignKey("ejercicios.id"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("diario_codigo", sa.String(12), nullable=False, server_default="VAR"),
        sa.Column("concepto", sa.String(200), nullable=False, server_default=""),
        sa.Column("estado", sa.String(12), nullable=False, server_default="REGISTRADO"),
        sa.Column("origen", sa.String(15), nullable=False, server_default="TRANSACCION"),
        sa.Column("transaccion_id", sa.Integer(), nullable=True),
        sa.Column("definicion_id", sa.Integer(), nullable=True),
        sa.Column("reversa_de", sa.Integer(), nullable=True),
        sa.Column("anulado_por_id", sa.Integer(), nullable=True),
        sa.Column("usuario", sa.String(60), nullable=False, server_default=""),
        sa.Column("creado_en", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ejercicio_id", "numero", name="uq_asiento_numero_ejercicio"),
    )
    for col in ("fecha", "diario_codigo", "estado", "origen", "transaccion_id", "ejercicio_id"):
        op.create_index(f"ix_asientos_{col}", "asientos", [col])
    op.create_table(
        "asientos_lineas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asiento_id", sa.Integer(), sa.ForeignKey("asientos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cuenta_codigo", sa.String(20), nullable=False),
        sa.Column("cuenta_nombre", sa.String(120), nullable=False, server_default=""),
        sa.Column("debe", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("haber", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("centro_codigo", sa.String(12), nullable=False, server_default=""),
        sa.Column("detalle", sa.String(200), nullable=False, server_default=""),
    )
    op.create_index("ix_lineas_asiento", "asientos_lineas", ["asiento_id"])
    op.create_index("ix_lineas_cuenta", "asientos_lineas", ["cuenta_codigo"])
    op.create_table(
        "transacciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modulo", sa.String(30), nullable=False),
        sa.Column("tipo", sa.String(60), nullable=False),
        sa.Column("referencia", sa.String(80), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False, server_default="ARS"),
        sa.Column("descripcion", sa.String(200), nullable=False, server_default=""),
        sa.Column("datos", postgresql.JSONB(), nullable=True),
        sa.Column("estado", sa.String(25), nullable=False, server_default="PENDIENTE_CONFIGURACION"),
        sa.Column("motivo", sa.String(300), nullable=False, server_default=""),
        sa.Column("asiento_id", sa.Integer(), sa.ForeignKey("asientos.id"), nullable=True),
        sa.Column("usuario_origen", sa.String(60), nullable=False, server_default=""),
        sa.Column("recibida_en", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("procesada_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("modulo", "tipo", "referencia", name="uq_transaccion_referencia"),
    )
    for col in ("modulo", "tipo", "referencia", "fecha", "estado"):
        op.create_index(f"ix_transacciones_{col}", "transacciones", [col])
    op.create_table(
        "comprobantes_iva",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("libro", sa.String(8), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo_comprobante", sa.String(4), nullable=False, server_default="01"),
        sa.Column("punto_venta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("numero", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cuit", sa.String(11), nullable=False, server_default=""),
        sa.Column("razon_social", sa.String(120), nullable=False, server_default=""),
        sa.Column("condicion_iva", sa.String(30), nullable=False, server_default=""),
        sa.Column("neto_gravado", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("neto_no_gravado", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("exento", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("alicuota", sa.Numeric(5, 2), nullable=False, server_default="21"),
        sa.Column("iva", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("percepciones", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("retenciones", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("transaccion_id", sa.Integer(), nullable=True),
        sa.Column("asiento_id", sa.Integer(), nullable=True),
        sa.Column("detalle", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint("libro", "tipo_comprobante", "punto_venta", "numero", "cuit",
                            name="uq_comprobante_iva"),
    )
    for col in ("libro", "fecha", "transaccion_id", "asiento_id"):
        op.create_index(f"ix_comprobantes_{col}", "comprobantes_iva", [col])


def downgrade():
    for t in ("comprobantes_iva", "transacciones", "asientos_lineas", "asientos",
              "definiciones_asiento", "ejercicios", "diarios", "centros_costo", "cuentas", "empresas"):
        op.drop_table(t)
