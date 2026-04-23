"""fix importe precision from Numeric(15,5) to Numeric(15,2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-12 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("liquidacion_detalle_raw", "importe",
                    type_=sa.Numeric(15, 2), existing_type=sa.Numeric(15, 5),
                    existing_nullable=False)
    op.alter_column("liquidacion_resumen_raw", "importe",
                    type_=sa.Numeric(15, 2), existing_type=sa.Numeric(15, 5),
                    existing_nullable=False)
    op.alter_column("liquidacion_validaciones", "expected_value",
                    type_=sa.Numeric(15, 2), existing_type=sa.Numeric(15, 5),
                    existing_nullable=True)
    op.alter_column("liquidacion_validaciones", "actual_value",
                    type_=sa.Numeric(15, 2), existing_type=sa.Numeric(15, 5),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column("liquidacion_detalle_raw", "importe",
                    type_=sa.Numeric(15, 5), existing_type=sa.Numeric(15, 2),
                    existing_nullable=False)
    op.alter_column("liquidacion_resumen_raw", "importe",
                    type_=sa.Numeric(15, 5), existing_type=sa.Numeric(15, 2),
                    existing_nullable=False)
    op.alter_column("liquidacion_validaciones", "expected_value",
                    type_=sa.Numeric(15, 5), existing_type=sa.Numeric(15, 2),
                    existing_nullable=True)
    op.alter_column("liquidacion_validaciones", "actual_value",
                    type_=sa.Numeric(15, 5), existing_type=sa.Numeric(15, 2),
                    existing_nullable=True)
