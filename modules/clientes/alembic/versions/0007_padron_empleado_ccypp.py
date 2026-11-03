"""padrón: marca de empleado de la Caja (LCAPRE del maestro viejo, "Empleado de C.C. y P.P.")

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("client_padron", sa.Column("empleado_ccypp", sa.Boolean(), nullable=False,
                                             server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("client_padron", "empleado_ccypp")
