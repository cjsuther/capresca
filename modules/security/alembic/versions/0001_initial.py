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
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(64), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
    )

    op.create_table(
        "modules",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
    )

    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("module_id", sa.Integer, sa.ForeignKey("modules.id"), nullable=False),
        sa.Column("code", sa.String(128), unique=True, nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
    )

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer, sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "user_permissions",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("permission_id", sa.Integer, sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("granted", sa.Boolean, default=True, nullable=False),
    )

    op.create_table(
        "token_blacklist",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("jti", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blacklisted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("token_blacklist")
    op.drop_table("user_permissions")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
    op.drop_table("modules")
    op.drop_table("roles")
    op.drop_table("users")
