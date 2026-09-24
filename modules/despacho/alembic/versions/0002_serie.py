"""La serie de numeración: cada área numera por su cuenta.

En el sistema anterior el correlativo corre por `TIPO_RES` (la serie: general, seguros, juegos…),
no por resolución/disposición: el mismo número aparece 11.700 veces en series distintas, así que sin
la serie una de cada cinco resoluciones no entraba. El código de modelo también se repite entre
series, y resolver el motivo sólo por código cruzaba los datos.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("modelos_resolucion",
                  sa.Column("serie", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_modelos_resolucion_serie", "modelos_resolucion", ["serie"])
    op.create_unique_constraint("uq_modelos_serie_codigo", "modelos_resolucion", ["serie", "codigo"])

    op.add_column("resoluciones",
                  sa.Column("serie", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_resoluciones_serie", "resoluciones", ["serie"])
    op.drop_constraint("uq_resoluciones_anio_tipo_numero", "resoluciones", type_="unique")
    op.create_unique_constraint("uq_resoluciones_anio_serie_numero", "resoluciones",
                                ["anio", "serie", "numero"])


def downgrade() -> None:
    op.drop_constraint("uq_resoluciones_anio_serie_numero", "resoluciones", type_="unique")
    op.create_unique_constraint("uq_resoluciones_anio_tipo_numero", "resoluciones",
                                ["anio", "tipo", "numero"])
    op.drop_index("ix_resoluciones_serie", "resoluciones")
    op.drop_column("resoluciones", "serie")

    op.drop_constraint("uq_modelos_serie_codigo", "modelos_resolucion", type_="unique")
    op.drop_index("ix_modelos_resolucion_serie", "modelos_resolucion")
    op.drop_column("modelos_resolucion", "serie")
