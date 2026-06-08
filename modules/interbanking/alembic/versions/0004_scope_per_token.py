"""scope per token, drop scope/grant_type from credentials

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-17 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Agregar scope a tokens
    op.add_column(
        "interbanking_tokens",
        sa.Column("scope", sa.String(64), nullable=True),
    )

    # 2) Backfill: tomar el scope de la credencial asociada (mejor esfuerzo)
    op.execute(
        """
        UPDATE interbanking_tokens t
        SET scope = c.scope
        FROM interbanking_credentials c
        WHERE t.credential_id = c.id
          AND t.scope IS NULL
        """
    )

    # 3) Invalidar tokens sin scope conocido (se regenerarán bajo demanda)
    op.execute("UPDATE interbanking_tokens SET is_active = false WHERE scope IS NULL")

    # 4) Quitar columnas obsoletas de credentials
    op.drop_column("interbanking_credentials", "scope")
    op.drop_column("interbanking_credentials", "grant_type")


def downgrade() -> None:
    op.add_column(
        "interbanking_credentials",
        sa.Column("scope", sa.String(255), nullable=True),
    )
    op.add_column(
        "interbanking_credentials",
        sa.Column(
            "grant_type",
            sa.String(30),
            nullable=False,
            server_default="password",
        ),
    )
    op.drop_column("interbanking_tokens", "scope")
