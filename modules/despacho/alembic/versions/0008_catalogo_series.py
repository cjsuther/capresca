"""Catálogo de series: pasan del código a la tabla `series` y se administran desde Catálogos.

Carga las cinco que estaban fijas en el código, con el mismo número, nombre y orden. Si los datos ya
usan otros números (TIPO_RES importados del sistema anterior que no estaban en la lista), también se
cargan, pero inactivos y como "Serie N", que es como se mostraban: no cambia nada de lo que se ve y
quedan para renombrarlos o activarlos desde la pantalla.

No es FK: un acto importado puede traer una serie que no esté en el catálogo.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-04
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Copia fija (la migración no importa la app): las que estaban en app/models.py hasta la 0007.
INICIALES = ((1, "GENERAL"), (3, "CRÉDITOS"), (6, "JUEGOS"), (4, "SEGUROS"), (5, "PROVEEDORES Y OBRAS"))


def upgrade() -> None:
    series = op.create_table(
        "series",
        sa.Column("numero", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("nombre", sa.String(60), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("nombre", name="uq_series_nombre"),
    )
    filas = [{"numero": n, "nombre": nombre, "orden": i, "activa": True}
             for i, (n, nombre) in enumerate(INICIALES, start=1)]

    con = op.get_bind()
    conocidas = {n for n, _ in INICIALES}
    usadas = set()
    for tabla in ("modelos_resolucion", "resoluciones", "numeracion_series"):
        usadas |= {r[0] for r in con.execute(sa.text(f"SELECT DISTINCT serie FROM {tabla}"))}
    orden = len(INICIALES)
    for n in sorted(x for x in usadas - conocidas if x is not None):
        orden += 1
        filas.append({"numero": n, "nombre": f"Serie {n}", "orden": orden, "activa": False})

    op.bulk_insert(series, filas)


def downgrade() -> None:
    op.drop_table("series")
