"""Auditoría central: qué hizo cada usuario con la información del sistema.

Un evento por acción. Vienen de dos lugares y se cruzan por `request_id`:
  - GATEWAY: toda operación que modifica datos, registrada automáticamente por el proxy (quién, qué
    módulo, qué operación, cuándo, desde dónde y si salió bien). Nadie se puede olvidar de auditar.
  - MODULO: el detalle del registro tocado (entidad, id y qué campos cambiaron), que manda el módulo.

La tabla es sólo-agregar: no hay API para editar ni borrar eventos (la purga por antigüedad es lo
único que los saca).
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

# Qué le pasó al dato. ACCION = operación de negocio que no es un ABM (aprobar, enviar, publicar…).
OPERACIONES = ("ALTA", "MODIFICACION", "BAJA", "ACCION", "ACCESO")
ORIGENES = ("GATEWAY", "MODULO")

JSONTipo = JSON().with_variant(JSONB, "postgresql")
# SQLite (tests) no autoincrementa un BIGINT: ahí la clave es INTEGER, en Postgres BIGINT.
IdTipo = BigInteger().with_variant(Integer, "sqlite")


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(IdTipo, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Quién
    usuario: Mapped[str] = mapped_column(String(60), default="", index=True)
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    # Dónde y qué
    modulo: Mapped[str] = mapped_column(String(30), default="", index=True)
    operacion: Mapped[str] = mapped_column(String(15), default="ACCION", index=True)
    entidad: Mapped[str] = mapped_column(String(60), default="", index=True)   # Contrato, Usuario, Lote…
    entidad_id: Mapped[str] = mapped_column(String(80), default="", index=True)
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    # Cómo llegó
    metodo: Mapped[str] = mapped_column(String(8), default="")                 # POST, PUT, DELETE…
    ruta: Mapped[str] = mapped_column(String(300), default="")
    estado_http: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exito: Mapped[bool | None] = mapped_column(nullable=True)
    origen: Mapped[str] = mapped_column(String(10), default="MODULO", index=True)
    request_id: Mapped[str] = mapped_column(String(40), default="", index=True)  # une gateway ↔ módulo
    # Qué cambió: {campo: [antes, después]} ya enmascarado
    cambios: Mapped[dict] = mapped_column(JSONTipo, default=dict)
    detalle: Mapped[str] = mapped_column(Text, default="")
