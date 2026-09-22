"""documentos del cliente (DNI, recibo, constancias)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("client_id", sa.Integer(), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="OTRO"),
        sa.Column("nombre", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("origen", sa.String(120), nullable=False, server_default="Carga manual"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_client_documents_id", "client_documents", ["id"])
    op.create_index("ix_client_documents_client_id", "client_documents", ["client_id"])
    op.create_index("ix_client_documents_sha256", "client_documents", ["sha256"])


def downgrade() -> None:
    op.drop_table("client_documents")
