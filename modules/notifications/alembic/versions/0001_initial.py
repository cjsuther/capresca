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
        "notifications",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(100), nullable=True),
        sa.Column("entity_id", sa.BigInteger, nullable=True),
        sa.Column("redirect_path", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by_module", sa.String(100), nullable=True),
    )
    op.create_index("idx_notifications_user_unread", "notifications", ["user_id", "is_read", "created_at"])
    op.create_index("idx_notifications_entity", "notifications", ["module", "entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_index("idx_notifications_entity")
    op.drop_index("idx_notifications_user_unread")
    op.drop_table("notifications")
