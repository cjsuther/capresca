"""Padrón de clientes migrado del sistema anterior (CCyPP / Visual FoxPro).

Tres piezas:

- `ClientPadron`: los datos del padrón que no son de identidad ni de domicilio (organismo, categoría,
  sueldo, situación de revista…). Van aparte para no ensanchar `clients`, que es el núcleo que usa
  todo el sistema.
- `ClientLegacyRef`: una fila por registro del DBF. En el sistema viejo la MISMA persona aparece una
  vez por organismo/categoría (el `CIDCLIENTE` es prefijo + CUIL: ACA…, AGC…, AGJ…), así que acá un
  cliente puede tener varias referencias. Sirve para no perder la trazabilidad con lo viejo.
- `ClientImport` / `ClientImportRechazo`: la importación en sí, con su avance y lo que quedó afuera.
"""
from sqlalchemy import (BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Integer,
                        Numeric, String, Text, func)
from sqlalchemy.orm import relationship

from app.db.base import Base

# Estados de una importación. Una INTERRUMPIDA es la que quedó a mitad de camino porque se reinició
# el módulo: los clientes que alcanzó a crear quedan, y se puede volver a subir el archivo (es
# idempotente por documento, así que no duplica).
IMPORT_PENDIENTE = "PENDIENTE"
IMPORT_PROCESANDO = "PROCESANDO"
IMPORT_TERMINADA = "TERMINADA"
IMPORT_ERROR = "ERROR"
IMPORT_INTERRUMPIDA = "INTERRUMPIDA"


class ClientPadron(Base):
    __tablename__ = "client_padron"

    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), primary_key=True)
    # NORGANO y ECUENTA vienen como N(12) en el padrón viejo: hay organismos de 12 dígitos.
    organismo_numero = Column(BigInteger, nullable=True, index=True)
    organismo_codigo = Column(String(3), nullable=True)
    categoria_numero = Column(Integer, nullable=True)
    categoria = Column(String(40), nullable=True)
    sueldo = Column(Numeric(12, 2), nullable=True)
    fecha_ingreso = Column(Date, nullable=True)          # FFPERM: alta en el organismo
    tipo_cliente = Column(Integer, nullable=True)
    situacion = Column(Integer, nullable=True)
    agente = Column(Integer, nullable=True)
    sucursal = Column(Integer, nullable=True)
    cuenta = Column(BigInteger, nullable=True)
    beneficio = Column(String(20), nullable=True)
    debito_automatico = Column(Boolean, nullable=False, default=False)
    baja = Column(Boolean, nullable=False, default=False)
    fecha_baja = Column(DateTime(timezone=True), nullable=True)
    motivo_baja = Column(String(60), nullable=True)
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    client = relationship("Client", backref="padron", uselist=False)


class ClientLegacyRef(Base):
    __tablename__ = "client_legacy_ref"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    # Clave del sistema viejo. Es única: si vuelve a venir, se actualiza la fila, no se agrega otra.
    cidcliente = Column(String(15), nullable=False, unique=True, index=True)
    organismo_numero = Column(BigInteger, nullable=True)
    beneficio = Column(String(20), nullable=True)
    tipo_cliente = Column(Integer, nullable=True)
    importacion_id = Column(Integer, ForeignKey("client_imports.id", ondelete="SET NULL"), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())


class ClientImport(Base):
    __tablename__ = "client_imports"

    id = Column(Integer, primary_key=True, index=True)
    archivo = Column(String(255), nullable=False)
    tamano = Column(Integer, nullable=False, default=0)
    sha256 = Column(String(64), nullable=True, index=True)
    estado = Column(String(15), nullable=False, default=IMPORT_PENDIENTE, index=True)
    total = Column(Integer, nullable=False, default=0)          # registros del DBF (sin los borrados)
    procesados = Column(Integer, nullable=False, default=0)
    creados = Column(Integer, nullable=False, default=0)
    actualizados = Column(Integer, nullable=False, default=0)
    rechazados = Column(Integer, nullable=False, default=0)
    mensaje = Column(Text, nullable=True)                        # error, si terminó mal
    usuario_id = Column(Integer, nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    terminado_en = Column(DateTime(timezone=True), nullable=True)

    rechazos = relationship("ClientImportRechazo", back_populates="importacion",
                            cascade="all, delete-orphan")


class ClientImportRechazo(Base):
    """Un registro que no se pudo importar, con el motivo. Se descarga en CSV para corregirlo en
    el origen; el archivo se vuelve a subir y los que ya estaban no se duplican."""
    __tablename__ = "client_import_rechazos"

    id = Column(Integer, primary_key=True, index=True)
    import_id = Column(Integer, ForeignKey("client_imports.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    fila = Column(Integer, nullable=False)
    cidcliente = Column(String(15), nullable=True)
    documento = Column(String(20), nullable=True)
    nombre = Column(String(60), nullable=True)
    motivo = Column(String(120), nullable=False)

    importacion = relationship("ClientImport", back_populates="rechazos")
