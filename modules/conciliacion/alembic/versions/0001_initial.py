"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_records",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("reconciliation_date", sa.Date, nullable=False),
        sa.Column("client_id", sa.Integer, nullable=False, index=True),
        sa.Column("agency_number", sa.String(20), nullable=True),
        sa.Column("agency_legal_name", sa.String(255), nullable=False),
        sa.Column("agency_tax_id", sa.String(30), nullable=True),
        sa.Column("importe_adeudado", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("importe_premios", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("importe_depositado", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="A_VERIFICAR"),
        sa.Column("modified_by_user_id", sa.Integer, nullable=True),
        sa.Column("modified_by_username", sa.String(100), nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("reconciliation_date", "client_id", name="uq_record_date_client"),
    )

    op.create_table(
        "reconciliation_ib_links",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("reconciliation_record_id", sa.BigInteger,
                  sa.ForeignKey("reconciliation_records.id"), nullable=False, index=True),
        sa.Column("ib_transaction_type", sa.String(20), nullable=False),
        sa.Column("ib_transaction_id", sa.BigInteger, nullable=False),
        sa.Column("ib_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("ib_cbu", sa.String(22), nullable=False),
        sa.Column("ib_concepto", sa.String(255), nullable=True),
        sa.Column("match_type", sa.String(20), nullable=False),
        sa.Column("linked_by_user_id", sa.Integer, nullable=False, server_default="0"),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("unlinked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unlinked_by_user_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("reconciliation_record_id", "ib_transaction_type", "ib_transaction_id",
                            name="uq_link_record_tx"),
    )
    op.create_index(
        "idx_ib_links_transaction",
        "reconciliation_ib_links",
        ["ib_transaction_type", "ib_transaction_id"],
        postgresql_where=sa.text("unlinked_at IS NULL"),
    )

    op.create_table(
        "reconciliation_status_history",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("reconciliation_record_id", sa.BigInteger,
                  sa.ForeignKey("reconciliation_records.id"), nullable=False, index=True),
        sa.Column("previous_status", sa.String(30), nullable=True),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("previous_importe_adeudado", sa.Numeric(15, 2), nullable=True),
        sa.Column("previous_importe_premios", sa.Numeric(15, 2), nullable=True),
        sa.Column("previous_importe_depositado", sa.Numeric(15, 2), nullable=True),
        sa.Column("new_importe_adeudado", sa.Numeric(15, 2), nullable=True),
        sa.Column("new_importe_premios", sa.Numeric(15, 2), nullable=True),
        sa.Column("new_importe_depositado", sa.Numeric(15, 2), nullable=True),
        sa.Column("changed_by_user_id", sa.Integer, nullable=False),
        sa.Column("changed_by_username", sa.String(100), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.Text, nullable=True),
    )

    op.create_table(
        "cbu_agency_cache",
        sa.Column("cbu", sa.String(22), primary_key=True),
        sa.Column("client_id", sa.Integer, nullable=False),
        sa.Column("agency_number", sa.String(20), nullable=True),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("cached_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "receipt_template_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("header_text", sa.Text, nullable=True),
        sa.Column("footer_text", sa.Text, nullable=True),
        sa.Column("logo_path", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("receipt_template_config")
    op.drop_table("cbu_agency_cache")
    op.drop_table("reconciliation_status_history")
    op.drop_index("idx_ib_links_transaction", "reconciliation_ib_links")
    op.drop_table("reconciliation_ib_links")
    op.drop_table("reconciliation_records")
