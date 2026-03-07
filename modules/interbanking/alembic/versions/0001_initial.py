"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interbanking_credentials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "interbanking_tokens",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("credential_id", sa.Integer, sa.ForeignKey("interbanking_credentials.id"), nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("token_type", sa.String(50), default="Bearer"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("obtained_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
    )

    op.create_table(
        "api_audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("username", sa.String(100)),
        sa.Column("credential_id", sa.Integer, sa.ForeignKey("interbanking_credentials.id"), nullable=True),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("http_method", sa.String(10)),
        sa.Column("endpoint", sa.String(255)),
        sa.Column("request_payload", JSONB),
        sa.Column("response_status", sa.Integer),
        sa.Column("response_payload", JSONB),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("success", sa.Boolean),
        sa.Column("error_message", sa.Text),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "transfers",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("audit_log_id", sa.BigInteger, sa.ForeignKey("api_audit_log.id"), nullable=True),
        sa.Column("cuenta_origen", sa.String(100)),
        sa.Column("cbu_destino", sa.String(22)),
        sa.Column("monto", sa.Numeric(15, 2)),
        sa.Column("concepto", sa.String(255)),
        sa.Column("id_operacion_ib", sa.String(100)),
        sa.Column("status", sa.String(50), default="INICIADA"),
        sa.Column("initiated_by", sa.Integer),
        sa.Column("initiated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_status_check", sa.DateTime(timezone=True)),
        sa.Column("last_status_payload", JSONB),
    )

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


def downgrade() -> None:
    op.drop_table("payment_batch_items")
    op.drop_table("payment_batches")
    op.drop_table("transfers")
    op.drop_table("api_audit_log")
    op.drop_table("interbanking_tokens")
    op.drop_table("interbanking_credentials")
