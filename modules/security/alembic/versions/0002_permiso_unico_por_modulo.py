"""El código de permiso es único POR MÓDULO, no global.

Con la unique global, dos módulos no podían declarar el mismo código (p.ej. `caja:read`): el seed
reusaba en silencio el permiso del otro módulo y el permiso quedaba colgado del módulo equivocado,
con lo que el gateway resolvía mal el acceso.

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("permissions_code_key", "permissions", type_="unique")
    op.create_unique_constraint("uq_permissions_module_code", "permissions", ["module_id", "code"])


def downgrade():
    op.drop_constraint("uq_permissions_module_code", "permissions", type_="unique")
    op.create_unique_constraint("permissions_code_key", "permissions", ["code"])
