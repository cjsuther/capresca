"""Las solicitudes del anexo dejan de copiarse acá: viven en Créditos.

Despacho emite el acto, pero la solicitud es de Créditos y él manda sobre ella. Tener la misma fila
en dos bases termina con las dos diciendo cosas distintas, así que Despacho la consulta por la API
interna de Créditos y esta tabla —que nunca llegó a cargarse— se retira.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("solicitudes_anexo")


def downgrade() -> None:
    op.create_table(
        "solicitudes_anexo",
        sa.Column("id", sa.Integer(), primary_key=True),
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
