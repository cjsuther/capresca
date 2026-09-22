"""Configuración compartida de Portezuelo: impuestos, índices de referencia, feriados y reglas del
workflow de aprobaciones.

Este módulo es el dueño de esos datos; los módulos que los usan (hoy Créditos) los leen por la API
interna (`/internal/configuraciones/*`) y no guardan copia propia.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Impuesto(Base):
    """Impuesto general (IVA, IIBB, sellado, percepciones). Créditos lo usa en el componente TAX."""
    __tablename__ = "impuestos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # IVA21, IIBB...
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="IVA")   # IVA, IIBB, SELLADO, PERCEPCION, RETENCION, OTRO
    alicuota: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)  # %
    base: Mapped[str] = mapped_column(String(20), default="INTERES")     # INTERES, CARGOS, CUOTA, CAPITAL, TOTAL
    cuenta_contable: Mapped[str] = mapped_column(String(12), default="")
    jurisdiccion: Mapped[str] = mapped_column(String(40), default="")     # para IIBB
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class IndiceReferencia(Base):
    """Índice para tasas variables (BADLAR, política monetaria, UVA…): tasa = índice + margen."""
    __tablename__ = "indices_referencia"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    valor: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)   # % nominal anual vigente
    fuente: Mapped[str] = mapped_column(String(60), default="")        # BCRA, INDEC...
    fecha_valor: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Feriado(Base):
    """Día no laborable de un país. El motor de cuotas de Créditos corre los vencimientos a día hábil."""
    __tablename__ = "feriados"
    __table_args__ = (UniqueConstraint("pais", "fecha", name="uq_feriados_pais_fecha"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pais: Mapped[str] = mapped_column(String(2), index=True, default="AR")  # ISO-3166 alpha-2
    fecha: Mapped[date] = mapped_column(Date, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20), default="INAMOVIBLE")    # INAMOVIBLE | TRASLADABLE | PUENTE
    origen: Mapped[str] = mapped_column(String(10), default="MANUAL")      # MANUAL | OFICIAL
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowRegla(Base):
    """Regla de aprobación de un tipo de objeto de un módulo (p.ej. créditos/LINEA).

    Acá vive sólo la DEFINICIÓN (niveles, rol que aprueba cada uno, cuatro-ojos, overrides). La
    ejecución —quién aprobó qué, con la unicidad por nivel— la hace el módulo dueño del objeto."""
    __tablename__ = "workflow_reglas"
    __table_args__ = (UniqueConstraint("modulo", "objeto", name="uq_workflow_regla_modulo_objeto"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    modulo: Mapped[str] = mapped_column(String(30), index=True)
    objeto: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(80), default="")
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=False)   # inactiva: no exige aprobación
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    niveles: Mapped[list["WorkflowNivel"]] = relationship(
        back_populates="regla", cascade="all, delete-orphan", order_by="WorkflowNivel.orden")


class WorkflowNivel(Base):
    """Nivel de aprobación en serie (orden 1..N). Aprueba quien tiene el ROL, con cuatro-ojos."""
    __tablename__ = "workflow_niveles"

    id: Mapped[int] = mapped_column(primary_key=True)
    regla_id: Mapped[int] = mapped_column(ForeignKey("workflow_reglas.id", ondelete="CASCADE"), index=True)
    orden: Mapped[int] = mapped_column(Integer, default=1)
    nombre: Mapped[str] = mapped_column(String(60), default="Aprobación")
    rol: Mapped[str] = mapped_column(String(20), default="APROBAR")   # APROBAR | SUPERVISAR
    cuatro_ojos: Mapped[bool] = mapped_column(Boolean, default=True)  # excluye a quien ya intervino
    regla: Mapped[WorkflowRegla] = relationship(back_populates="niveles")
    usuarios: Mapped[list["WorkflowNivelUsuario"]] = relationship(
        back_populates="nivel", cascade="all, delete-orphan", order_by="WorkflowNivelUsuario.username")


class WorkflowNivelUsuario(Base):
    """Override por usuario en un nivel: INCLUIR (aprueba aunque no tenga el rol) o EXCLUIR (no aprueba
    aunque lo tenga)."""
    __tablename__ = "workflow_nivel_usuarios"
    __table_args__ = (UniqueConstraint("nivel_id", "username", name="uq_workflow_nivel_usuario"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nivel_id: Mapped[int] = mapped_column(ForeignKey("workflow_niveles.id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(60))
    modo: Mapped[str] = mapped_column(String(10), default="INCLUIR")  # INCLUIR | EXCLUIR
    nivel: Mapped[WorkflowNivel] = relationship(back_populates="usuarios")
