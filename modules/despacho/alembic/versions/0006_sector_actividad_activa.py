"""Sector y actividad de modelos y actos, y actos inactivos.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for tabla in ("modelos_resolucion", "resoluciones"):
        op.add_column(tabla, sa.Column("sector", sa.String(80), nullable=False, server_default=""))
        op.add_column(tabla, sa.Column("actividad", sa.String(80), nullable=False, server_default=""))
        op.create_index(f"ix_{tabla}_sector", tabla, ["sector"])
        op.create_index(f"ix_{tabla}_actividad", tabla, ["actividad"])
    op.add_column("resoluciones", sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index("ix_resoluciones_activa", "resoluciones", ["activa"])


def downgrade() -> None:
    op.drop_index("ix_resoluciones_activa", "resoluciones")
    op.drop_column("resoluciones", "activa")
    for tabla in ("modelos_resolucion", "resoluciones"):
        op.drop_index(f"ix_{tabla}_actividad", tabla)
        op.drop_index(f"ix_{tabla}_sector", tabla)
        op.drop_column(tabla, "actividad")
        op.drop_column(tabla, "sector")
