"""Tesorería: lotes de pagos que llegan de otros módulos (o se cargan a mano), se aprueban según el
workflow y se envían por Interbanking.

Estados del lote:   PENDIENTE_APROBACION → APROBADO → ENVIADO → CONFIRMADO | CON_ERRORES
                    PENDIENTE_APROBACION → RECHAZADO
Estados del pago:   PENDIENTE → ENVIANDO → ENVIADO → CONFIRMADO | FALLIDO
                    PENDIENTE → EXCLUIDO (lo saca el tesorero antes de aprobar)
                    ENVIANDO → INCIERTO (se cortó la comunicación: no se sabe si salió; lo resuelve una
                    persona, nunca se reintenta solo, así no se paga dos veces)
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
                        func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

ORIGENES = ("CREDITOS", "CONCILIACION", "MANUAL")


class Lote(Base):
    __tablename__ = "lotes"
    __table_args__ = (UniqueConstraint("origen", "referencia_origen", name="uq_lote_origen_referencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)       # LOT-2026-00001
    origen: Mapped[str] = mapped_column(String(20), index=True)                    # CREDITOS | CONCILIACION | MANUAL
    referencia_origen: Mapped[str] = mapped_column(String(80))                     # p.ej. "liquidación 2026-09-22"
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    callback_url: Mapped[str | None] = mapped_column(String(300), nullable=True)   # a quién avisar el resultado
    estado: Mapped[str] = mapped_column(String(25), default="PENDIENTE_APROBACION", index=True)
    motivo_rechazo: Mapped[str] = mapped_column(String(300), default="")
    simulado: Mapped[bool] = mapped_column(Boolean, default=False)                  # se envió en modo simulación
    creado_por: Mapped[str] = mapped_column(String(60), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    aprobado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enviado_por: Mapped[str] = mapped_column(String(60), default="")
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pagos: Mapped[list["Pago"]] = relationship(back_populates="lote", cascade="all, delete-orphan",
                                               order_by="Pago.id")
    aprobaciones: Mapped[list["LoteAprobacion"]] = relationship(back_populates="lote", cascade="all, delete-orphan",
                                                                order_by="LoteAprobacion.nivel_orden")


class Pago(Base):
    __tablename__ = "pagos"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    referencia_externa: Mapped[str] = mapped_column(String(80), index=True)   # id del contrato, registro, etc.
    beneficiario: Mapped[str] = mapped_column(String(160))
    documento: Mapped[str] = mapped_column(String(20), default="")            # CUIT / CUIL / DNI
    cbu: Mapped[str] = mapped_column(String(22))
    monto: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    concepto: Mapped[str] = mapped_column(String(120), default="")
    estado: Mapped[str] = mapped_column(String(15), default="PENDIENTE", index=True)
    motivo: Mapped[str] = mapped_column(String(300), default="")             # exclusión / error del banco
    transfer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)   # id local en Interbanking
    id_operacion_ib: Mapped[str] = mapped_column(String(80), default="")
    estado_banco: Mapped[str] = mapped_column(String(40), default="")
    enviado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notificado: Mapped[str] = mapped_column(String(15), default="")         # último estado avisado al origen
    lote: Mapped[Lote] = relationship(back_populates="pagos")


class LoteAprobacion(Base):
    """Un nivel del workflow aprobado. La DB es el árbitro: un nivel se aprueba una sola vez."""
    __tablename__ = "lote_aprobaciones"
    __table_args__ = (UniqueConstraint("lote_id", "nivel_orden", name="uq_lote_aprobacion_nivel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    nivel_orden: Mapped[int] = mapped_column(Integer)
    aprobado_por: Mapped[str] = mapped_column(String(60))
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    lote: Mapped[Lote] = relationship(back_populates="aprobaciones")


class Evento(Base):
    """Bitácora del lote: quién hizo qué y cuándo (alta, exclusiones, aprobaciones, envío, resultados)."""
    __tablename__ = "lote_eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    usuario: Mapped[str] = mapped_column(String(60), default="")
    accion: Mapped[str] = mapped_column(String(40))
    detalle: Mapped[str] = mapped_column(Text, default="")
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
