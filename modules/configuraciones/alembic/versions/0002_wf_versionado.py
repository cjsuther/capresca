"""Workflow gráfico versionado: wf_proceso y wf_version.

Sólo crea las tablas. NO toca ni borra `workflow_reglas`/`workflow_niveles`/`workflow_nivel_usuarios`:
siguen siendo lo que lee la API interna de Créditos y Tesorería.

La carga de las reglas actuales como versión 1 PUBLICADA la hace `app.seed` (corre después de
`alembic upgrade head` en el arranque del contenedor) con `wf_procesos.sincronizar_procesos`: es
idempotente y no depende de que el modelo ORM coincida con el esquema de esta revisión.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wf_proceso",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("modulo", sa.String(30), nullable=False),
        sa.Column("objeto", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(80), nullable=False, server_default=""),
        sa.Column("descripcion", sa.String(200), nullable=False, server_default=""),
        sa.Column("habilitado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("creado_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("modulo", "objeto", name="uq_wf_proceso_modulo_objeto"),
    )
    op.create_index("ix_wf_proceso_modulo", "wf_proceso", ["modulo"])

    op.create_table(
        "wf_version",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proceso_id", sa.Integer(), sa.ForeignKey("wf_proceso.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False, server_default="BORRADOR"),
        sa.Column("grafo", sa.JSON(), nullable=False),
        sa.Column("layout", sa.JSON(), nullable=False),
        sa.Column("huella", sa.String(64), nullable=False, server_default=""),
        sa.Column("nota", sa.String(300), nullable=False, server_default=""),
        sa.Column("diff_resumen", sa.Text(), nullable=False, server_default=""),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("basada_en", sa.Integer(), nullable=True),
        sa.Column("creada_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("creada_en", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("modificada_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("modificada_en", sa.DateTime(), nullable=True),
        sa.Column("publicada_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("publicada_en", sa.DateTime(), nullable=True),
        sa.Column("retirada_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("retirada_en", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("proceso_id", "numero", name="uq_wf_version_numero"),
    )
    op.create_index("ix_wf_version_proceso_id", "wf_version", ["proceso_id"])
    op.create_index("ix_wf_version_estado", "wf_version", ["estado"])
    op.create_index("uq_wf_version_publicada", "wf_version", ["proceso_id"], unique=True,
                    postgresql_where=sa.text("estado = 'PUBLICADA'"), sqlite_where=sa.text("estado = 'PUBLICADA'"))
    op.create_index("uq_wf_version_borrador", "wf_version", ["proceso_id"], unique=True,
                    postgresql_where=sa.text("estado = 'BORRADOR'"), sqlite_where=sa.text("estado = 'BORRADOR'"))


def downgrade() -> None:
    # Sólo las tablas nuevas: las reglas viejas quedan como estaban.
    op.drop_table("wf_version")
    op.drop_table("wf_proceso")
