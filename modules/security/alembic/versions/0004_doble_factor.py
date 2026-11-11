"""Doble factor (TOTP con TokenServer): marca local de 2FA activo por usuario.

La marca es la que decide, sin depender de TokenServer, si el login pide el código: así, si TokenServer
no responde, a quien tiene 2FA se le niega el ingreso (falla cerrado) en vez de dejarlo pasar.
Idempotente: no hace nada si las columnas ya existen. Reversible con `alembic downgrade 0003`.

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _columnas() -> set:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}


def upgrade():
    cols = _columnas()
    if "totp_activo" not in cols:
        op.add_column("users", sa.Column("totp_activo", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "totp_activado_en" not in cols:
        op.add_column("users", sa.Column("totp_activado_en", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    cols = _columnas()
    if "totp_activado_en" in cols:
        op.drop_column("users", "totp_activado_en")
    if "totp_activo" in cols:
        op.drop_column("users", "totp_activo")
