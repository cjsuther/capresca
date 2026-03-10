"""add agency_number and client_cbus

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
    op.add_column("legal_clients", sa.Column("agency_number", sa.String(20), nullable=True))
    op.create_unique_constraint("uq_legal_clients_agency_number", "legal_clients", ["agency_number"])

    op.create_table(
        "client_cbus",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("cbu", sa.String(22), nullable=False, unique=True, index=True),
        sa.Column("alias", sa.String(100), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("account_type", sa.String(50), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.Integer, nullable=False),
    )
    op.create_index("idx_client_cbus_active", "client_cbus", ["cbu"],
                    postgresql_where=sa.text("is_active = TRUE"))


def downgrade() -> None:
    op.drop_index("idx_client_cbus_active", "client_cbus")
    op.drop_table("client_cbus")
    op.drop_constraint("uq_legal_clients_agency_number", "legal_clients", type_="unique")
    op.drop_column("legal_clients", "agency_number")
