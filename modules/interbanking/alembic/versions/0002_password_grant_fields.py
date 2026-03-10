"""add password grant fields to credentials

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interbanking_credentials", sa.Column("auth_url", sa.String(255), nullable=True))
    op.add_column("interbanking_credentials", sa.Column("username", sa.String(255), nullable=True))
    op.add_column("interbanking_credentials", sa.Column("password_encrypted", sa.Text, nullable=True))
    op.add_column("interbanking_credentials", sa.Column("scope", sa.String(255), nullable=True))
    op.add_column("interbanking_credentials", sa.Column("service_url", sa.String(512), nullable=True))
    # client_secret_encrypted ya no es obligatorio
    op.alter_column("interbanking_credentials", "client_secret_encrypted", nullable=True)


def downgrade() -> None:
    op.alter_column("interbanking_credentials", "client_secret_encrypted", nullable=False)
    op.drop_column("interbanking_credentials", "service_url")
    op.drop_column("interbanking_credentials", "scope")
    op.drop_column("interbanking_credentials", "password_encrypted")
    op.drop_column("interbanking_credentials", "username")
    op.drop_column("interbanking_credentials", "auth_url")
