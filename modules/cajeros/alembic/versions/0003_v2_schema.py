"""v2 schema: authorization_rules and transactions

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "authorization_rules",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cajero_user_id", sa.Integer, nullable=False, index=True),
        sa.Column("cajero_username", sa.String(100), nullable=True),
        sa.Column("authorizer_user_id", sa.Integer, nullable=False, index=True),
        sa.Column("authorizer_username", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("amount_limit", sa.Numeric(15, 2), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer, nullable=False),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("cajero_user_id", sa.Integer, nullable=False, index=True),
        sa.Column("cajero_username", sa.String(100), nullable=True),
        sa.Column("authorizer_user_id", sa.Integer, nullable=True, index=True),
        sa.Column("authorizer_username", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="PROCESADA"),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer, nullable=False),
    )

    op.create_table(
        "transaction_rule_triggers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("transaction_id", sa.BigInteger, sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("rule_id", sa.Integer, sa.ForeignKey("authorization_rules.id"), nullable=False),
        sa.Column("authorizer_user_id", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("transaction_rule_triggers")
    op.drop_table("transactions")
    op.drop_table("authorization_rules")
