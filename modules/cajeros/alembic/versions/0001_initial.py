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
        "user_limits",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("daily_limit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("per_transaction_limit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="ARS"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "authorization_relations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cajero_user_id", sa.Integer, nullable=False, index=True),
        sa.Column("authorizer_user_id", sa.Integer, nullable=False, index=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "authorization_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cajero_user_id", sa.Integer, nullable=False, index=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="ARS"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", "EXPIRED", name="requeststatus"),
                  nullable=False, server_default="PENDING"),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("authorizer_user_id", sa.Integer, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text, nullable=True),
    )

    op.create_table(
        "authorized_operations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("request_id", sa.Integer, sa.ForeignKey("authorization_requests.id"), nullable=False, unique=True),
        sa.Column("executed_by_user_id", sa.Integer, nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("authorized_operations")
    op.drop_table("authorization_requests")
    op.drop_table("authorization_relations")
    op.drop_table("user_limits")
    op.execute("DROP TYPE IF EXISTS requeststatus")
