"""Desde qué número sigue cada serie en el año (continúa la numeración del sistema anterior).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "numeracion_series",
        sa.Column("anio", sa.Integer(), primary_key=True),
        sa.Column("serie", sa.Integer(), primary_key=True),
        sa.Column("desde_numero", sa.Integer(), nullable=True),
        sa.Column("desde_oficial", sa.Integer(), nullable=True),
        sa.Column("actualizado_por", sa.String(60), nullable=False, server_default=""),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("numeracion_series")
