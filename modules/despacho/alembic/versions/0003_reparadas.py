"""Cuántos textos completó la importación de una corrida anterior.

La primera versión del importador no extraía del ZIP los archivos de memo (.fpt), donde vive el
cuerpo de los instrumentos: las tablas entraban completas pero sin texto. Volver a subir el archivo
ahora los completa, y este contador deja ver cuántos reparó.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("importaciones_despacho",
                  sa.Column("reparadas", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("importaciones_despacho", "reparadas")
