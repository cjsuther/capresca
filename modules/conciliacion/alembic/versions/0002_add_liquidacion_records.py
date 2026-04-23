"""add liquidacion conciliacion records

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "liquidacion_conciliacion_records",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("liquidacion_batch_id", sa.Integer, nullable=False),
        sa.Column("agency_number", sa.String(6), nullable=False),
        sa.Column("operation_date", sa.Date, nullable=True),
        sa.Column("importe_adeudado", sa.Numeric(15, 2), nullable=False),
        sa.Column("importe_premios", sa.Numeric(15, 2), nullable=False),
        sa.Column("recaudacion_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("comision_total", sa.Numeric(15, 2), nullable=False),
        sa.Column("resumen_number", sa.String(20), nullable=True),
        sa.Column("moneda", sa.String(5), nullable=True),
        sa.Column("reconciliation_record_id", sa.BigInteger,
                  sa.ForeignKey("reconciliation_records.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_liq_conc_batch", "liquidacion_conciliacion_records", ["liquidacion_batch_id"])
    op.create_index("idx_liq_conc_agency_date", "liquidacion_conciliacion_records", ["agency_number", "operation_date"])


def downgrade() -> None:
    op.drop_index("idx_liq_conc_agency_date", "liquidacion_conciliacion_records")
    op.drop_index("idx_liq_conc_batch", "liquidacion_conciliacion_records")
    op.drop_table("liquidacion_conciliacion_records")
