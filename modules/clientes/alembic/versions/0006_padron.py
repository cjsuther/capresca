"""padrón de clientes migrado del sistema anterior (CCyPP/VFP) e importaciones

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Domicilio completo (el padrón viejo trae barrio, departamento y CP) y el CUIL, que es con lo
    # que se unifica la persona (en el maestro viejo aparece una vez por organismo).
    op.add_column("clients", sa.Column("neighborhood", sa.String(64), nullable=True))
    op.add_column("clients", sa.Column("department", sa.String(64), nullable=True))
    op.add_column("clients", sa.Column("postal_code", sa.String(12), nullable=True))
    op.add_column("human_clients", sa.Column("cuil", sa.String(11), nullable=True))
    op.create_index("ix_human_clients_cuil", "human_clients", ["cuil"])

    op.create_table(
        "client_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("archivo", sa.String(255), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("estado", sa.String(15), nullable=False, server_default="PENDIENTE"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("procesados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actualizados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rechazados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mensaje", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("terminado_en", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_client_imports_estado", "client_imports", ["estado"])
    op.create_index("ix_client_imports_sha256", "client_imports", ["sha256"])
    op.create_index("ix_client_imports_creado_en", "client_imports", ["creado_en"])

    op.create_table(
        "client_import_rechazos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("import_id", sa.Integer(),
                  sa.ForeignKey("client_imports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fila", sa.Integer(), nullable=False),
        sa.Column("cidcliente", sa.String(15), nullable=True),
        sa.Column("documento", sa.String(20), nullable=True),
        sa.Column("nombre", sa.String(60), nullable=True),
        sa.Column("motivo", sa.String(120), nullable=False),
    )
    op.create_index("ix_client_import_rechazos_import_id", "client_import_rechazos", ["import_id"])

    op.create_table(
        "client_padron",
        sa.Column("client_id", sa.Integer(),
                  sa.ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True),
        # NORGANO/ECUENTA son N(12) en el DBF: hay organismos de 12 dígitos, no entran en integer.
        sa.Column("organismo_numero", sa.BigInteger(), nullable=True),
        sa.Column("organismo_codigo", sa.String(3), nullable=True),
        sa.Column("categoria_numero", sa.Integer(), nullable=True),
        sa.Column("categoria", sa.String(40), nullable=True),
        sa.Column("sueldo", sa.Numeric(12, 2), nullable=True),
        sa.Column("fecha_ingreso", sa.Date(), nullable=True),
        sa.Column("tipo_cliente", sa.Integer(), nullable=True),
        sa.Column("situacion", sa.Integer(), nullable=True),
        sa.Column("agente", sa.Integer(), nullable=True),
        sa.Column("sucursal", sa.Integer(), nullable=True),
        sa.Column("cuenta", sa.BigInteger(), nullable=True),
        sa.Column("beneficio", sa.String(20), nullable=True),
        sa.Column("debito_automatico", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("baja", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("fecha_baja", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_baja", sa.String(60), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_client_padron_organismo", "client_padron", ["organismo_numero"])

    op.create_table(
        "client_legacy_ref",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(),
                  sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cidcliente", sa.String(15), nullable=False),
        sa.Column("organismo_numero", sa.BigInteger(), nullable=True),
        sa.Column("beneficio", sa.String(20), nullable=True),
        sa.Column("tipo_cliente", sa.Integer(), nullable=True),
        sa.Column("importacion_id", sa.Integer(),
                  sa.ForeignKey("client_imports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_client_legacy_ref_client_id", "client_legacy_ref", ["client_id"])
    op.create_index("ix_client_legacy_ref_cidcliente", "client_legacy_ref", ["cidcliente"],
                    unique=True)


def downgrade() -> None:
    op.drop_table("client_legacy_ref")
    op.drop_table("client_padron")
    op.drop_table("client_import_rechazos")
    op.drop_table("client_imports")
    op.drop_index("ix_human_clients_cuil", table_name="human_clients")
    op.drop_column("human_clients", "cuil")
    op.drop_column("clients", "postal_code")
    op.drop_column("clients", "department")
    op.drop_column("clients", "neighborhood")
