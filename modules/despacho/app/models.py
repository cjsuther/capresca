"""Despacho: resoluciones y disposiciones, sus modelos, el anexo y los expedientes.

Viene del módulo Despacho del sistema anterior (VFP): `Despacho/rtf.dbf` (modelos),
`resoluciones.dbf`, `beneficiarios.dbf` y los expedientes de mesa de entradas.

Las dos numeraciones de un acto administrativo, que es lo particular del circuito:

- **Número correlativo**: se asigna al crear, único por (año, SERIE). Es el número de trabajo.
- **Número real**: el OFICIAL, que Despacho carga después, cuando el acto vuelve firmado. Tiene su
  propia numeración por (año, serie) y su propia fecha.

La **serie** (VFP: `TIPO_RES`) es el área que emite el acto y cada una numera por su cuenta: en el
backup del sistema anterior el mismo número aparece 11.700 veces en series distintas, así que sin
ella una de cada cinco resoluciones se perdería. `tipo` sigue distinguiendo resolución de
disposición (VFP: `DISPOSICIO`), que es otra cosa: la clase de instrumento.

Un acto firmado, con número real o anulado es inmutable: no se altera algo ya emitido.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

TIPOS = ("RES", "DIS")                 # Resolución / Disposición

# Series de numeración del despacho (VFP: TIPO_RES). Los nombres salen de los modelos que usa cada
# una en el sistema anterior; el número es el que manda, el nombre es sólo la etiqueta en pantalla.
SERIES = {
    1: "General (créditos y ayudas sociales)",
    3: "Préstamos y garantías",
    4: "Seguros",
    5: "Proveedores y obras",
    6: "Juegos",
}
SERIE_POR_DEFECTO = 1


def nombre_serie(serie: int) -> str:
    return SERIES.get(serie, f"Serie {serie}")


BORRADOR, FIRMADA = "B", "F"


class ModeloResolucion(Base):
    """Plantilla de resolución o disposición (VFP: rtf.dbf). Es el catálogo que alimenta el combo
    "Modelo a utilizar": su descripción pasa a ser el MOTIVO del acto y su cuerpo, el texto inicial."""
    __tablename__ = "modelos_resolucion"
    # El mismo código existe en varias series (el 3 es "ayudas sociales" en la 1 y "transf. lotimax"
    # en la 6): resolver el motivo sólo por código cruzaba los datos.
    __table_args__ = (UniqueConstraint("serie", "codigo", name="uq_modelos_serie_codigo"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[int] = mapped_column(Integer, index=True, default=0)     # COD_MOD (se repite entre series)
    serie: Mapped[int] = mapped_column(Integer, index=True, default=SERIE_POR_DEFECTO)   # TIPO_RES
    descripcion: Mapped[str] = mapped_column(String(120), default="")       # DES_MOD → motivo del acto
    tipo: Mapped[str] = mapped_column(String(3), default="RES")             # RES | DIS (DISPOSICIO)
    es_seguros: Mapped[bool] = mapped_column(Boolean, default=False)        # SEGUROS
    plantilla: Mapped[str] = mapped_column(Text, default="")                # MODELO (HTML del cuerpo)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def tiene_plantilla(self) -> bool:
        return bool((self.plantilla or "").strip())

    @property
    def serie_nombre(self) -> str:
        return nombre_serie(self.serie)


class Resolucion(Base):
    """Resolución / Disposición administrativa (VFP: resoluciones.dbf)."""
    __tablename__ = "resoluciones"
    # El correlativo es único por año y serie, y la DB es el árbitro (no un lock aplicativo).
    __table_args__ = (UniqueConstraint("anio", "serie", "numero", name="uq_resoluciones_anio_serie_numero"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, index=True)                # NRO_RES (correlativo)
    anio: Mapped[int] = mapped_column(Integer, index=True)
    tipo: Mapped[str] = mapped_column(String(3), default="RES", index=True)
    serie: Mapped[int] = mapped_column(Integer, default=SERIE_POR_DEFECTO, index=True)    # TIPO_RES
    fecha: Mapped[date] = mapped_column(Date)                               # FEC_RES
    # Número oficial: se carga después, cuando el acto vuelve firmado. Puede quedar vacío.
    numero_real: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)   # NRO_REAL
    fecha_real: Mapped[date | None] = mapped_column(Date, nullable=True)                  # FEC_REAL
    organo: Mapped[str] = mapped_column(String(60), default="")
    asunto: Mapped[str] = mapped_column(String(200), default="")
    motivo_codigo: Mapped[int] = mapped_column(Integer, default=0)          # COD_MOT
    motivo: Mapped[str] = mapped_column(String(120), default="")            # descripción del modelo
    importe: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    modelo_id: Mapped[int | None] = mapped_column(ForeignKey("modelos_resolucion.id"), nullable=True)
    origen: Mapped[str] = mapped_column(String(40), default="")             # expediente / nota de origen
    nro_op: Mapped[int | None] = mapped_column(Integer, nullable=True)      # orden de pago asociada
    texto: Mapped[str] = mapped_column(Text, default="")                    # cuerpo del instrumento (HTML)
    estado: Mapped[str] = mapped_column(String(1), default=BORRADOR, index=True)
    anulada: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_anulacion: Mapped[str] = mapped_column(String(200), default="")
    creado_por: Mapped[str] = mapped_column(String(60), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    beneficiarios: Mapped[list["ResolucionBeneficiario"]] = relationship(
        back_populates="resolucion", cascade="all, delete-orphan")

    @property
    def serie_nombre(self) -> str:
        return nombre_serie(self.serie)

    @property
    def oficial(self) -> bool:
        """Ya emitido: firmado, con número real o anulado. No se toca más."""
        return self.estado == FIRMADA or self.numero_real is not None or self.anulada


class ResolucionBeneficiario(Base):
    """A quién alcanza el acto (VFP: beneficiarios.dbf). Es la grilla al pie de la resolución."""
    __tablename__ = "resolucion_beneficiarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    resolucion_id: Mapped[int] = mapped_column(ForeignKey("resoluciones.id", ondelete="CASCADE"), index=True)
    tipo_doc: Mapped[int] = mapped_column(Integer, default=0)
    nro_doc: Mapped[str] = mapped_column(String(11), default="", index=True)
    nombre: Mapped[str] = mapped_column(String(80), default="")
    tipo_bene: Mapped[int] = mapped_column(Integer, default=0)
    importe: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)

    resolucion: Mapped["Resolucion"] = relationship(back_populates="beneficiarios")


class Expediente(Base):
    """Expediente que circula por pases entre oficinas (mesa de entradas)."""
    __tablename__ = "expedientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    caratula: Mapped[str] = mapped_column(String(200))
    iniciador: Mapped[str] = mapped_column(String(80), default="")
    fecha_inicio: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(1), default="T", index=True)   # T en trámite, A archivado
    oficina_actual: Mapped[str] = mapped_column(String(60), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pases: Mapped[list["Pase"]] = relationship(
        back_populates="expediente", cascade="all, delete-orphan",
        order_by="Pase.id")


class Pase(Base):
    """Movimiento del expediente de una oficina a otra. La historia no se borra ni se edita."""
    __tablename__ = "pases"

    id: Mapped[int] = mapped_column(primary_key=True)
    expediente_id: Mapped[int] = mapped_column(ForeignKey("expedientes.id", ondelete="CASCADE"), index=True)
    fecha: Mapped[date] = mapped_column(Date)
    oficina_origen: Mapped[str] = mapped_column(String(60), default="")
    oficina_destino: Mapped[str] = mapped_column(String(60), default="")
    motivo: Mapped[str] = mapped_column(String(200), default="")
    usuario: Mapped[str] = mapped_column(String(60), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    expediente: Mapped["Expediente"] = relationship(back_populates="pases")


# --------------------------------------------------------------------------- importación
IMPORT_PENDIENTE = "PENDIENTE"
IMPORT_PROCESANDO = "PROCESANDO"
IMPORT_TERMINADA = "TERMINADA"
IMPORT_ERROR = "ERROR"
IMPORT_INTERRUMPIDA = "INTERRUMPIDA"


class ImportacionDespacho(Base):
    """Traída de los DBF del sistema anterior (modelos, resoluciones y beneficiarios)."""
    __tablename__ = "importaciones_despacho"

    id: Mapped[int] = mapped_column(primary_key=True)
    archivo: Mapped[str] = mapped_column(String(255))
    tamano: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(15), default=IMPORT_PENDIENTE, index=True)
    modelos: Mapped[int] = mapped_column(Integer, default=0)
    resoluciones: Mapped[int] = mapped_column(Integer, default=0)
    beneficiarios: Mapped[int] = mapped_column(Integer, default=0)
    solicitudes: Mapped[int] = mapped_column(Integer, default=0)
    omitidas: Mapped[int] = mapped_column(Integer, default=0)        # ya existían (es idempotente)
    reparadas: Mapped[int] = mapped_column(Integer, default=0)       # textos completados de otra corrida
    mensaje: Mapped[str] = mapped_column(Text, default="")
    usuario_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    terminado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
