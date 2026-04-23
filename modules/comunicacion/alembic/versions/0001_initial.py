"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("client_id", sa.Integer, nullable=True, index=True),
        sa.Column("client_name", sa.String(255), nullable=True),
        sa.Column("client_phone", sa.String(20), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_preview", sa.String(255), nullable=True),
        sa.Column("unread_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("assigned_to_user_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_conversations_last_msg", "conversations", ["last_message_at"])
    op.create_index(
        "idx_conversations_unread",
        "conversations",
        ["unread_count"],
        postgresql_where=sa.text("unread_count > 0"),
    )
    op.create_index(
        "idx_conversations_unlinked",
        "conversations",
        ["client_id"],
        postgresql_where=sa.text("client_id IS NULL"),
    )

    # -- messages
    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("conversation_id", sa.BigInteger, sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("message_type", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("media_url", sa.String(1000), nullable=True),
        sa.Column("media_mime_type", sa.String(100), nullable=True),
        sa.Column("media_filename", sa.String(255), nullable=True),
        sa.Column("media_local_path", sa.String(500), nullable=True),
        sa.Column("wa_message_id", sa.String(100), unique=True, nullable=True),
        sa.Column("wa_status", sa.String(20), nullable=True),
        sa.Column("wa_error_code", sa.String(20), nullable=True),
        sa.Column("wa_error_message", sa.Text, nullable=True),
        sa.Column("sent_by_user_id", sa.Integer, nullable=True),
        sa.Column("sent_by_username", sa.String(100), nullable=True),
        sa.Column("sent_by_module", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("interactive_reply_id", sa.String(100), nullable=True),
        sa.Column("interactive_reply_title", sa.String(255), nullable=True),
    )
    op.create_index("idx_messages_conversation", "messages", ["conversation_id", "created_at"])
    op.create_index("idx_messages_wa_id", "messages", ["wa_message_id"])

    # -- whatsapp_config
    op.create_table(
        "whatsapp_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("phone_number_id", sa.String(50), nullable=False),
        sa.Column("business_account_id", sa.String(50), nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("webhook_verify_token", sa.String(255), nullable=False),
        sa.Column("display_phone_number", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by_user_id", sa.Integer, nullable=True),
    )

    # -- interactive_menu_config
    op.create_table(
        "interactive_menu_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "greeting_text",
            sa.Text,
            nullable=False,
            server_default="Hola! Bienvenido a Portezuelo. Seleccione una opcion:",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.Integer, nullable=True),
    )

    # -- interactive_menu_options
    op.create_table(
        "interactive_menu_options",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "menu_id",
            sa.Integer,
            sa.ForeignKey("interactive_menu_config.id"),
            nullable=False,
        ),
        sa.Column("option_id", sa.String(50), nullable=False),
        sa.Column("title", sa.String(60), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("action_payload", JSONB, nullable=False),
        sa.Column("requires_client", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("idx_menu_options_order", "interactive_menu_options", ["menu_id", "sort_order"])
    op.create_unique_constraint("uq_menu_option_id", "interactive_menu_options", ["menu_id", "option_id"])


def downgrade() -> None:
    op.drop_table("interactive_menu_options")
    op.drop_table("interactive_menu_config")
    op.drop_table("whatsapp_config")
    op.drop_table("messages")
    op.drop_table("conversations")
