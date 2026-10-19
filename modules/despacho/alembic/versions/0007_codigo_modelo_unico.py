"""El código del modelo no se repite en todo el catálogo (antes era único por serie).

Los modelos importados del sistema anterior repetían código entre series: el más antiguo (menor id)
conserva su código y los demás pasan al siguiente libre.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    con = op.get_bind()
    filas = con.execute(sa.text("SELECT id, codigo FROM modelos_resolucion ORDER BY id")).all()
    usados: set[int] = set()
    repetidos = []
    for id_, codigo in filas:
        if codigo in usados or not codigo or codigo < 1:
            repetidos.append(id_)
        else:
            usados.add(codigo)
    siguiente = max(usados, default=0) + 1
    for id_ in repetidos:
        con.execute(sa.text("UPDATE modelos_resolucion SET codigo = :c WHERE id = :i"),
                    {"c": siguiente, "i": id_})
        siguiente += 1
    op.drop_constraint("uq_modelos_serie_codigo", "modelos_resolucion", type_="unique")
    op.create_unique_constraint("uq_modelos_codigo", "modelos_resolucion", ["codigo"])


def downgrade() -> None:
    # Los códigos renumerados no vuelven atrás: siguen siendo únicos, también por serie.
    op.drop_constraint("uq_modelos_codigo", "modelos_resolucion", type_="unique")
    op.create_unique_constraint("uq_modelos_serie_codigo", "modelos_resolucion", ["serie", "codigo"])
