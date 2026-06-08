"""initial schema legacy module

Revision ID: 0001
Revises:
Create Date: 2026-06-08 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Control: registro de interacciones (ledger IN/OUT) ──────────────
    op.create_table(
        "legacy_interaction_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("direction", sa.String(3), nullable=False, index=True),
        sa.Column("database", sa.String(20), nullable=False, index=True),
        sa.Column("table_name", sa.String(50), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
        sa.Column("occurred_date", sa.Date, nullable=False, index=True),
        sa.Column("rows_affected", sa.Integer, nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="OK"),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("origin_module", sa.String(50), nullable=True),
        sa.Column("origin_user_id", sa.Integer, nullable=True),
        sa.Column("outbox_id", sa.BigInteger, nullable=True, index=True),
        sa.Column("payload_summary", postgresql.JSONB, nullable=True),
    )
    op.create_index("ix_interaction_db_date", "legacy_interaction_log", ["database", "occurred_date"])

    # ── Control: estado de sincronización por tabla ─────────────────────
    op.create_table(
        "legacy_sync_state",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("table_name", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("database", sa.String(20), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(10), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("rows_seen", sa.Integer, nullable=True),
        sa.Column("rows_changed", sa.Integer, nullable=True),
        sa.Column("watermark", sa.String(100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Control: outbox de escrituras hacia el legacy ───────────────────
    op.create_table(
        "legacy_outbox",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("database", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True, index=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="PENDING", index=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("origin_module", sa.String(50), nullable=True),
        sa.Column("origin_user_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── Mirrors: juegos ─────────────────────────────────────────────────
    op.create_table(
        "mirror_maeagencias",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("cod_agencia", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("titular", sa.String(120), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "mirror_maejuegos",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("cod_juego", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("descripcion", sa.String(120), nullable=True),
        sa.Column("modalidad", sa.Integer, nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Mirrors: caja ───────────────────────────────────────────────────
    op.create_table(
        "mirror_cajaliq",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("cod_agencia", sa.String(10), nullable=False),
        sa.Column("cod_juego", sa.Integer, nullable=True),
        sa.Column("no_sorteo", sa.Integer, nullable=True),
        sa.Column("importe", sa.Numeric(15, 2), nullable=True),
        sa.Column("intereses", sa.Numeric(15, 2), nullable=True),
        sa.Column("pagado", sa.Boolean, nullable=True),
        sa.Column("fecha_pago", sa.Date, nullable=True),
        sa.Column("no_recibo", sa.Integer, nullable=True, index=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("cod_agencia", "cod_juego", "no_sorteo", name="uq_mirror_cajaliq_natural"),
    )
    op.create_table(
        "mirror_cajapagos",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("no_recibo", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("cod_agencia", sa.String(10), nullable=True, index=True),
        sa.Column("fecha_pago", sa.Date, nullable=True, index=True),
        sa.Column("origen", sa.String(20), nullable=True),
        sa.Column("total", sa.Numeric(15, 2), nullable=True),
        sa.Column("bonos", sa.Numeric(15, 2), nullable=True),
        sa.Column("pesos", sa.Numeric(15, 2), nullable=True),
        sa.Column("cajero", sa.String(50), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "mirror_cajaforpag",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("no_recibo", sa.Integer, nullable=False, index=True),
        sa.Column("sno_recibo", sa.Integer, nullable=True),
        sa.Column("moneda", sa.String(5), nullable=True),
        sa.Column("origen", sa.String(20), nullable=True),
        sa.Column("fecha_pago", sa.Date, nullable=True),
        sa.Column("anulado", sa.Boolean, nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("no_recibo", "sno_recibo", name="uq_mirror_cajaforpag_natural"),
    )
    op.create_table(
        "mirror_cajacreseg",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("nrecibo", sa.Integer, nullable=True, index=True),
        sa.Column("recofi", sa.Integer, nullable=True),
        sa.Column("origen", sa.String(20), nullable=True),
        sa.Column("fecha_pago", sa.Date, nullable=True, index=True),
        sa.Column("via_pago", sa.String(20), nullable=True),
        sa.Column("usuario_pago", sa.String(50), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Mirrors: creditos ───────────────────────────────────────────────
    op.create_table(
        "mirror_maeclientes",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("cuil", sa.String(15), nullable=True, index=True),
        sa.Column("nombre", sa.String(120), nullable=True),
        sa.Column("domicilio", sa.String(120), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "mirror_solicitud",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("no_credito", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("cuil", sa.String(15), nullable=True, index=True),
        sa.Column("estado", sa.String(2), nullable=True),
        sa.Column("monto", sa.Numeric(15, 2), nullable=True),
        sa.Column("tasa", sa.Numeric(8, 4), nullable=True),
        sa.Column("ga_cuil", sa.String(15), nullable=True),
        sa.Column("g2_cuil", sa.String(15), nullable=True),
        sa.Column("g3_cuil", sa.String(15), nullable=True),
        sa.Column("g4_cuil", sa.String(15), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "mirror_maecuotas",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("no_credito", sa.Integer, nullable=False, index=True),
        sa.Column("no_cuota", sa.Integer, nullable=False),
        sa.Column("estado", sa.String(2), nullable=True),
        sa.Column("fecha_vto", sa.Date, nullable=True, index=True),
        sa.Column("total_vdo", sa.Numeric(15, 2), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("no_credito", "no_cuota", name="uq_mirror_maecuotas_natural"),
    )
    op.create_table(
        "mirror_lineacred",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("cod_linea", sa.Integer, nullable=False, unique=True, index=True),
        sa.Column("descripcion", sa.String(120), nullable=True),
        sa.Column("nmoradia", sa.Numeric(8, 4), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Mirrors: general ────────────────────────────────────────────────
    op.create_table(
        "mirror_maestrodio",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("legajo", sa.String(20), nullable=True, index=True),
        sa.Column("cuil", sa.String(15), nullable=True, index=True),
        sa.Column("nombre", sa.String(120), nullable=True),
        sa.Column("haberes", sa.Numeric(15, 2), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "mirror_organismos",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("cod_organismo", sa.String(20), nullable=True, unique=True, index=True),
        sa.Column("descripcion", sa.String(120), nullable=True),
        sa.Column("capresca", sa.String(5), nullable=True),
        sa.Column("row_hash", sa.String(32), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "mirror_organismos",
        "mirror_maestrodio",
        "mirror_lineacred",
        "mirror_maecuotas",
        "mirror_solicitud",
        "mirror_maeclientes",
        "mirror_cajacreseg",
        "mirror_cajaforpag",
        "mirror_cajapagos",
        "mirror_cajaliq",
        "mirror_maejuegos",
        "mirror_maeagencias",
        "legacy_outbox",
        "legacy_sync_state",
    ]:
        op.drop_table(table)
    op.drop_index("ix_interaction_db_date", table_name="legacy_interaction_log")
    op.drop_table("legacy_interaction_log")
