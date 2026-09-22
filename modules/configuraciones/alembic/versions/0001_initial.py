"""Esquema inicial: impuestos, índices, feriados y workflow.

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
        "impuestos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="IVA"),
        sa.Column("alicuota", sa.Numeric(9, 4), nullable=False, server_default="0"),
        sa.Column("base", sa.String(20), nullable=False, server_default="INTERES"),
        sa.Column("cuenta_contable", sa.String(12), nullable=False, server_default=""),
        sa.Column("jurisdiccion", sa.String(40), nullable=False, server_default=""),
        sa.Column("vigente_desde", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_impuestos_codigo", "impuestos", ["codigo"], unique=True)

    op.create_table(
        "indices_referencia",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("valor", sa.Numeric(9, 4), nullable=False, server_default="0"),
        sa.Column("fuente", sa.String(60), nullable=False, server_default=""),
        sa.Column("fecha_valor", sa.Date(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_indices_referencia_codigo", "indices_referencia", ["codigo"], unique=True)

    op.create_table(
        "feriados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pais", sa.String(2), nullable=False, server_default="AR"),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="INAMOVIBLE"),
        sa.Column("origen", sa.String(10), nullable=False, server_default="MANUAL"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("pais", "fecha", name="uq_feriados_pais_fecha"),
    )
    op.create_index("ix_feriados_pais", "feriados", ["pais"])
    op.create_index("ix_feriados_fecha", "feriados", ["fecha"])

    op.create_table(
        "workflow_reglas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modulo", sa.String(30), nullable=False),
        sa.Column("objeto", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False, server_default=""),
        sa.Column("descripcion", sa.String(200), nullable=False, server_default=""),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("modulo", "objeto", name="uq_workflow_regla_modulo_objeto"),
    )
    op.create_index("ix_workflow_reglas_modulo", "workflow_reglas", ["modulo"])

    op.create_table(
        "workflow_niveles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("regla_id", sa.Integer(), sa.ForeignKey("workflow_reglas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("nombre", sa.String(60), nullable=False, server_default="Aprobación"),
        sa.Column("rol", sa.String(20), nullable=False, server_default="APROBAR"),
        sa.Column("cuatro_ojos", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_workflow_niveles_regla_id", "workflow_niveles", ["regla_id"])

    op.create_table(
        "workflow_nivel_usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nivel_id", sa.Integer(), sa.ForeignKey("workflow_niveles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("username", sa.String(60), nullable=False),
        sa.Column("modo", sa.String(10), nullable=False, server_default="INCLUIR"),
        sa.UniqueConstraint("nivel_id", "username", name="uq_workflow_nivel_usuario"),
    )
    op.create_index("ix_workflow_nivel_usuarios_nivel_id", "workflow_nivel_usuarios", ["nivel_id"])


def downgrade() -> None:
    for t in ("workflow_nivel_usuarios", "workflow_niveles", "workflow_reglas",
              "feriados", "indices_referencia", "impuestos"):
        op.drop_table(t)
