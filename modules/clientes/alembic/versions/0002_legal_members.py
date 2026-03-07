"""legal client members

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_client_members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("legal_client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("human_client_id", sa.Integer, sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("role", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("legal_client_id", "human_client_id", name="uq_legal_human_member"),
    )


def downgrade() -> None:
    op.drop_table("legal_client_members")
