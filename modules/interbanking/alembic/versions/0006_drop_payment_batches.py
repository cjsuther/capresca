"""drop payment_batches and payment_batch_items

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-18 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("payment_batch_items")
    op.drop_table("payment_batches")


def downgrade() -> None:
    op.create_table(
        "payment_batches",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("audit_log_id", sa.BigInteger, sa.ForeignKey("api_audit_log.id"), nullable=True),
        sa.Column("descripcion", sa.String(255)),
        sa.Column("id_lote_ib", sa.String(100)),
        sa.Column("status", sa.String(50), default="BORRADOR"),
        sa.Column("total_items", sa.Integer),
        sa.Column("total_amount", sa.Numeric(15, 2)),
        sa.Column("created_by", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("last_status_check", sa.DateTime(timezone=True)),
        sa.Column("last_status_payload", JSONB),
    )
    op.create_table(
        "payment_batch_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.BigInteger, sa.ForeignKey("payment_batches.id"), nullable=False),
        sa.Column("cbu", sa.String(22)),
        sa.Column("monto", sa.Numeric(15, 2)),
        sa.Column("detalle", sa.String(255)),
        sa.Column("status_item", sa.String(50)),
    )
