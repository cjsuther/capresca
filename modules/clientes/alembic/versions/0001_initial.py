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
        "clients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_type", sa.Enum("HUMAN", "LEGAL", name="clienttype"), nullable=False),
        sa.Column("code", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("country", sa.String(64), nullable=True, server_default="AR"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by_user_id", sa.Integer, nullable=True),
    )

    op.create_table(
        "human_clients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("last_name", sa.String(128), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=True),
        sa.Column("document_number", sa.String(64), nullable=True),
        sa.Column("birth_date", sa.String(16), nullable=True),
        sa.Column("gender", sa.String(16), nullable=True),
        sa.Column("nationality", sa.String(64), nullable=True),
    )

    op.create_table(
        "legal_clients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255), nullable=True),
        sa.Column("tax_id", sa.String(64), nullable=True),
        sa.Column("tax_id_type", sa.String(32), nullable=True),
        sa.Column("incorporation_date", sa.String(16), nullable=True),
        sa.Column("legal_representative", sa.String(255), nullable=True),
        sa.Column("industry_sector", sa.String(128), nullable=True),
    )

    op.create_table(
        "client_contacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("contact_type", sa.String(32), nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
    )

    op.create_table(
        "client_notes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("client_notes")
    op.drop_table("client_contacts")
    op.drop_table("legal_clients")
    op.drop_table("human_clients")
    op.drop_table("clients")
    op.execute("DROP TYPE IF EXISTS clienttype")
