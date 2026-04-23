"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-11 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "liquidacion_batches",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("zip_filename", sa.String(255), nullable=False),
        sa.Column("operation_date", sa.Date, nullable=True),
        sa.Column("resumen_number", sa.String(20), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDIENTE"),
        sa.Column("total_detail_records", sa.Integer, nullable=True),
        sa.Column("total_summary_records", sa.Integer, nullable=True),
        sa.Column("total_agencies", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_by", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_to_conciliacion_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "liquidacion_detalle_raw",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("liquidacion_batches.id"), nullable=False, index=True),
        sa.Column("n_agen", sa.String(6), nullable=False),
        sa.Column("c_juego", sa.String(6), nullable=False),
        sa.Column("d_juego", sa.String(20), nullable=False),
        sa.Column("n_sorteo", sa.String(5), nullable=False),
        sa.Column("c_codigo", sa.String(3), nullable=False),
        sa.Column("d_codigo", sa.String(50), nullable=False),
        sa.Column("d_operac", sa.String(10), nullable=False),
        sa.Column("importe", sa.Numeric(15, 5), nullable=False),
        sa.Column("c_moneda", sa.String(2), nullable=True),
        sa.Column("c_resumen", sa.String(10), nullable=True),
    )

    op.create_table(
        "liquidacion_resumen_raw",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("liquidacion_batches.id"), nullable=False, index=True),
        sa.Column("c_juego", sa.String(3), nullable=False),
        sa.Column("n_agen", sa.String(6), nullable=False),
        sa.Column("d_operac", sa.String(10), nullable=False),
        sa.Column("importe", sa.Numeric(15, 5), nullable=False),
        sa.Column("c_moneda", sa.String(2), nullable=True),
        sa.Column("c_resumen", sa.String(10), nullable=True),
        sa.Column("f_movin", sa.String(5), nullable=True),
    )

    op.create_table(
        "liquidacion_procesadas",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("liquidacion_batches.id"), nullable=False, index=True),
        sa.Column("n_agen", sa.String(6), nullable=False),
        sa.Column("c_juego", sa.Integer, nullable=False),
        sa.Column("d_juego", sa.String(50), nullable=True),
        sa.Column("n_sorteo", sa.Integer, nullable=False),
        sa.Column("modalidad", sa.Integer, nullable=False, server_default="0"),
        sa.Column("moneda", sa.String(5), nullable=True),
        sa.Column("recaudacion", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("premios", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("comision", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("fdo_gtia", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("ing_brutos", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("debitos", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("creditos", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("no_recibo", sa.Integer, nullable=True),
        sa.Column("operation_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("batch_id", "n_agen", "c_juego", "n_sorteo", "modalidad",
                            name="uq_procesada_batch_agen_juego_sorteo_mod"),
    )

    op.create_table(
        "liquidacion_archivos",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("liquidacion_batches.id"), nullable=False, index=True),
        sa.Column("file_type", sa.String(30), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("file_data", sa.LargeBinary, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "liquidacion_validaciones",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("liquidacion_batches.id"), nullable=False, index=True),
        sa.Column("validation_type", sa.String(50), nullable=False),
        sa.Column("agency_number", sa.String(6), nullable=True),
        sa.Column("expected_value", sa.Numeric(15, 5), nullable=True),
        sa.Column("actual_value", sa.Numeric(15, 5), nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("detail_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("liquidacion_validaciones")
    op.drop_table("liquidacion_archivos")
    op.drop_table("liquidacion_procesadas")
    op.drop_table("liquidacion_resumen_raw")
    op.drop_table("liquidacion_detalle_raw")
    op.drop_table("liquidacion_batches")
