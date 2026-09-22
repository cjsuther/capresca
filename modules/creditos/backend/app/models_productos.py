"""Modelos de la plataforma de productos de préstamo (estilo Temenos AA).

Deriva del modelo lógico de `Codex/prestamos/outputs/schema-productos-prestamos-postgresql.sql`.
Se namespacian las tablas con prefijo ``pp_`` para no colisionar con el dominio legacy
(que ya tiene `lineas`, `creditos`, etc.). IDs string (uuid4) y tipos portables para que
el mismo modelo corra en Postgres (app) y SQLite (tests).

Fase 3: catálogo + versiones + pricing + componentes. La simulación/cuotas se calcula
server-side on-the-fly (no se persiste todavía).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    String, Integer, Numeric, Boolean, DateTime, Date, ForeignKey, Text, JSON, func,
    LargeBinary, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uid() -> str:
    return str(uuid4())


class PPMoneda(Base):
    __tablename__ = "pp_moneda"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    codigo_iso: Mapped[str] = mapped_column(String(3), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    simbolo: Mapped[str] = mapped_column(String(8), default="$")
    decimales: Mapped[int] = mapped_column(Integer, default=2)


class PPCalculador(Base):
    __tablename__ = "pp_calculador"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)  # FRANCES, ALEMAN...
    nombre: Mapped[str] = mapped_column(String(120))
    familia: Mapped[str] = mapped_column(String(40), default="AMORTIZACION")
    certificado: Mapped[bool] = mapped_column(Boolean, default=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    versiones: Mapped[list["PPCalculadorVersion"]] = relationship(back_populates="calculador")


class PPCalculadorVersion(Base):
    __tablename__ = "pp_calculador_version"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    calculador_id: Mapped[str] = mapped_column(ForeignKey("pp_calculador.id"))
    numero_version: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[str] = mapped_column(String(20), default="PUBLICADO")
    motor: Mapped[str] = mapped_column(String(30), default="CERTIFICADO")
    precision_decimal: Mapped[int] = mapped_column(Integer, default=10)
    regla_redondeo: Mapped[str] = mapped_column(String(30), default="HALF_UP")
    checksum: Mapped[str] = mapped_column(String(128), default="")
    calculador: Mapped["PPCalculador"] = relationship(back_populates="versiones")


class PPComponenteDefinicion(Base):
    __tablename__ = "pp_componente_definicion"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str] = mapped_column(String(40))
    permite_multiples: Mapped[bool] = mapped_column(Boolean, default=False)
    requerido: Mapped[bool] = mapped_column(Boolean, default=False)
    orden: Mapped[int] = mapped_column(Integer, default=1)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class PPLinea(Base):
    __tablename__ = "pp_linea"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class PPGrupo(Base):
    __tablename__ = "pp_grupo"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    linea_id: Mapped[str] = mapped_column(ForeignKey("pp_linea.id"))
    codigo: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class PPFamilia(Base):
    __tablename__ = "pp_familia"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    grupo_id: Mapped[str] = mapped_column(ForeignKey("pp_grupo.id"))
    codigo: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class PPProducto(Base):
    """Padre estable del producto. Las condiciones viven en las versiones."""
    __tablename__ = "pp_producto"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    familia_id: Mapped[str] = mapped_column(ForeignKey("pp_familia.id"))
    padre_id: Mapped[str | None] = mapped_column(ForeignKey("pp_producto.id"), nullable=True)  # herencia
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(160))
    descripcion: Mapped[str] = mapped_column(Text, default="")
    copiado_de: Mapped[str | None] = mapped_column(String(36), nullable=True)  # H-190: código del préstamo del que se duplicó (trazabilidad + prompt de retirar-original)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    versiones: Mapped[list["PPVersion"]] = relationship(
        back_populates="producto", cascade="all, delete-orphan")


class PPVersion(Base):
    """Condiciones comerciales versionadas. Una versión PUBLICADA es inmutable."""
    __tablename__ = "pp_producto_version"
    # Nº de versión correlativo por producto: unicidad (producto_id, numero_version) por la DB. H-108.
    __table_args__ = (UniqueConstraint("producto_id", "numero_version", name="uq_pp_version_producto_numero"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    producto_id: Mapped[str] = mapped_column(ForeignKey("pp_producto.id"))
    numero_version: Mapped[int] = mapped_column(Integer, default=1)
    estado: Mapped[str] = mapped_column(String(20), default="BORRADOR")  # BORRADOR..RETIRADO
    derivada_de: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vigente_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigente_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    moneda_id: Mapped[str] = mapped_column(ForeignKey("pp_moneda.id"))
    calculador_version_id: Mapped[str] = mapped_column(ForeignKey("pp_calculador_version.id"))
    # Condiciones tipadas (TERM_AMOUNT + REPAYMENT_SCHEDULE)
    monto_minimo: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    monto_maximo: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    plazo_minimo: Mapped[int] = mapped_column(Integer, default=1)
    plazo_maximo: Mapped[int] = mapped_column(Integer, default=1)
    unidad_plazo: Mapped[str] = mapped_column(String(20), default="CUOTAS")
    frecuencia_pago: Mapped[str] = mapped_column(String(20), default="MENSUAL")
    base_dias: Mapped[str] = mapped_column(String(20), default="ACT/365")
    regla_feriados: Mapped[str] = mapped_column(String(30), default="SIGUIENTE_HABIL")
    gracia_capital: Mapped[int] = mapped_column(Integer, default=0)
    gracia_interes: Mapped[int] = mapped_column(Integer, default=0)
    permite_prepago: Mapped[bool] = mapped_column(Boolean, default=True)
    cfg_heredada: Mapped[bool] = mapped_column(Boolean, default=False)  # condiciones core heredadas del padre
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Auditoría del workflow de aprobación (Fase 4)
    enviado_por: Mapped[str | None] = mapped_column(String(30), nullable=True)
    aprobado_por: Mapped[str | None] = mapped_column(String(30), nullable=True)
    publicado_por: Mapped[str | None] = mapped_column(String(30), nullable=True)
    producto: Mapped["PPProducto"] = relationship(back_populates="versiones")
    tasas: Mapped[list["PPTasa"]] = relationship(
        back_populates="version", cascade="all, delete-orphan")
    cargos: Mapped[list["PPCargo"]] = relationship(
        back_populates="version", cascade="all, delete-orphan")
    componentes: Mapped[list["PPComponente"]] = relationship(
        back_populates="version", cascade="all, delete-orphan")


class PPTasa(Base):
    __tablename__ = "pp_producto_tasa"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    producto_version_id: Mapped[str] = mapped_column(ForeignKey("pp_producto_version.id"))
    codigo: Mapped[str] = mapped_column(String(50))  # TNA, MORA
    modalidad: Mapped[str] = mapped_column(String(20), default="FIJA")
    tasa_default: Mapped[Decimal] = mapped_column(Numeric(16, 6), default=0)
    periodicidad: Mapped[str] = mapped_column(String(20), default="ANUAL")
    indice_referencia: Mapped[str] = mapped_column(String(30), default="")  # código del maestro de índices
    margen: Mapped[Decimal] = mapped_column(Numeric(16, 6), default=0)       # para tasa variable
    # Reglas de negociación (Fase B): banda dentro de la cual se puede negociar al originar
    tasa_minima: Mapped[Decimal] = mapped_column(Numeric(16, 6), default=0)
    tasa_maxima: Mapped[Decimal] = mapped_column(Numeric(16, 6), default=0)
    negociable: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped["PPVersion"] = relationship(back_populates="tasas")


class PPCargo(Base):
    __tablename__ = "pp_producto_cargo"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    producto_version_id: Mapped[str] = mapped_column(ForeignKey("pp_producto_version.id"))
    codigo: Mapped[str] = mapped_column(String(50))  # OTORGAMIENTO
    nombre: Mapped[str] = mapped_column(String(120), default="")
    porcentaje: Mapped[Decimal] = mapped_column(Numeric(16, 6), default=0)
    momento_aplicacion: Mapped[str] = mapped_column(String(30), default="DESEMBOLSO")
    version: Mapped["PPVersion"] = relationship(back_populates="cargos")


class PPComponente(Base):
    __tablename__ = "pp_producto_componente"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    producto_version_id: Mapped[str] = mapped_column(ForeignKey("pp_producto_version.id"))
    componente_codigo: Mapped[str] = mapped_column(String(60))
    orden: Mapped[int] = mapped_column(Integer, default=1)
    requerido: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    heredado: Mapped[bool] = mapped_column(Boolean, default=False)  # config heredada del padre
    version: Mapped["PPVersion"] = relationship(back_populates="componentes")


# ===================== Contrato / arrangement (Fase 5) y servicing (Fase 6) =====================
class PPContrato(Base):
    """Instancia del producto aceptada por un cliente. Congela snapshot del producto."""
    __tablename__ = "pp_contrato"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    producto_id: Mapped[str] = mapped_column(ForeignKey("pp_producto.id"))
    producto_version_numero: Mapped[int] = mapped_column(Integer)
    numero_contrato: Mapped[str] = mapped_column(String(40), unique=True)
    cliente_nombre: Mapped[str] = mapped_column(String(160))
    sistema: Mapped[str] = mapped_column(String(20))
    monto_original: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    saldo_capital: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    plazo: Mapped[int] = mapped_column(Integer)
    tasa_contratada: Mapped[Decimal] = mapped_column(Numeric(16, 6))
    fecha_valor: Mapped[date] = mapped_column(Date)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), default="ACTIVO")  # ACTIVO..CERRADO
    snapshot_producto: Mapped[dict] = mapped_column(JSON, default=dict)
    # Datos adicionales de la originación (destino, CBU de acreditación, garante, observaciones)
    datos_adicionales: Mapped[dict] = mapped_column(JSON, default=dict)
    # Origen legacy: NO_SOLICIT de la solicitud de crédito real (VFP) que dio lugar al contrato
    solicitud_origen: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    creado_por: Mapped[str] = mapped_column(String(30), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    cuotas: Mapped[list["PPCuotaContrato"]] = relationship(
        back_populates="contrato", cascade="all, delete-orphan")
    actividades: Mapped[list["PPActividad"]] = relationship(
        back_populates="contrato", cascade="all, delete-orphan")


class PPCuotaContrato(Base):
    __tablename__ = "pp_cuota_contrato"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    contrato_id: Mapped[str] = mapped_column(ForeignKey("pp_contrato.id"))
    numero_cuota: Mapped[int] = mapped_column(Integer)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), default="PENDIENTE")  # PENDIENTE, PAGADA
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    capital: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    interes: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    cargos: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)   # comisiones + impuestos (total)
    impuestos: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)  # porción de impuestos dentro de cargos
    total: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    saldo_final: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    pagado: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    devengada: Mapped[bool] = mapped_column(Boolean, default=False)  # interés ya reconocido (devengo)
    contrato: Mapped["PPContrato"] = relationship(back_populates="cuotas")


class PPActividad(Base):
    """Servicing: desembolso, pago, prepago, payoff, cambio de tasa, etc."""
    __tablename__ = "pp_actividad"
    # Una actividad se reversa UNA sola vez: unicidad de reversa_de (los NULL —no-reversas— conviven).
    # La DB es árbitro contra dos reversar concurrentes de la misma actividad (doble contra-asiento). H-110.
    __table_args__ = (UniqueConstraint("reversa_de", name="uq_pp_actividad_reversa_de"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    contrato_id: Mapped[str] = mapped_column(ForeignKey("pp_contrato.id"))
    tipo: Mapped[str] = mapped_column(String(40))  # DISBURSEMENT, PAYMENT, PAYOFF, REVERSAL...
    fecha: Mapped[date] = mapped_column(Date)  # fecha valor (permite backdating)
    importe: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    estado: Mapped[str] = mapped_column(String(20), default="EJECUTADA")  # EJECUTADA, REVERSADA
    # Fase F: reversa de actividad — apunta a la actividad revertida (la entrada REVERSAL)
    reversa_de: Mapped[str | None] = mapped_column(ForeignKey("pp_actividad.id"), nullable=True)
    dato: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # datos extra (Fase G: repricing)
    detalle: Mapped[str] = mapped_column(String(300), default="")
    creado_por: Mapped[str] = mapped_column(String(30), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    contrato: Mapped["PPContrato"] = relationship(back_populates="actividades")


class PPSimulacion(Base):
    """Simulación de crédito guardada (what-if sobre una línea) con su cronograma."""
    __tablename__ = "pp_simulacion"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    producto_id: Mapped[str] = mapped_column(ForeignKey("pp_producto.id"), index=True)
    producto_version_numero: Mapped[int] = mapped_column(Integer)
    etiqueta: Mapped[str] = mapped_column(String(120), default="")
    sistema: Mapped[str] = mapped_column(String(20))
    monto: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    plazo: Mapped[int] = mapped_column(Integer)
    tna: Mapped[Decimal] = mapped_column(Numeric(16, 6))
    cargo_pct: Mapped[Decimal] = mapped_column(Numeric(9, 4), default=0)
    total_cuotas: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    total_interes: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    primera_cuota: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    creado_por: Mapped[str] = mapped_column(String(30), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    cuotas: Mapped[list["PPCuotaSimulada"]] = relationship(
        back_populates="simulacion", cascade="all, delete-orphan")


class PPCuotaSimulada(Base):
    __tablename__ = "pp_cuota_simulada"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    simulacion_id: Mapped[str] = mapped_column(ForeignKey("pp_simulacion.id"), index=True)
    numero_cuota: Mapped[int] = mapped_column(Integer)
    fecha_vencimiento: Mapped[date] = mapped_column(Date)
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    capital: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    interes: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    cargos: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    saldo_final: Mapped[Decimal] = mapped_column(Numeric(19, 4))
    simulacion: Mapped["PPSimulacion"] = relationship(back_populates="cuotas")


class PPBundle(Base):
    """Fase G: paquete de productos ofrecidos juntos (préstamo + complementos)."""
    __tablename__ = "pp_bundle"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nombre: Mapped[str] = mapped_column(String(160))
    descripcion: Mapped[str] = mapped_column(String(300), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    items: Mapped[list["PPBundleItem"]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan")


class PPBundleItem(Base):
    __tablename__ = "pp_bundle_item"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    bundle_id: Mapped[str] = mapped_column(ForeignKey("pp_bundle.id"))
    producto_id: Mapped[str] = mapped_column(ForeignKey("pp_producto.id"))
    rol: Mapped[str] = mapped_column(String(30), default="PRINCIPAL")  # PRINCIPAL | COMPLEMENTO
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=True)
    orden: Mapped[int] = mapped_column(Integer, default=1)
    bundle: Mapped["PPBundle"] = relationship(back_populates="items")


class PPSolicitud(Base):
    """Solicitud de crédito de la línea nueva (product builder). Cliente registrado o alta express.

    Workflow con cuatro-ojos: BORRADOR → EN_EVALUACION → APROBADA → ORIGINADA (o RECHAZADA/ANULADA).
    Una solicitud APROBADA alimenta la originación (crea un PPContrato y queda ORIGINADA).
    """
    __tablename__ = "pp_solicitud"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    estado: Mapped[str] = mapped_column(String(20), default="BORRADOR", index=True)
    solicitante_tipo: Mapped[str] = mapped_column(String(15), default="REGISTRADO")  # REGISTRADO | NO_REGISTRADO
    cliente_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)   # maestro real
    cliente_datos: Mapped[dict] = mapped_column(JSON, default=dict)   # alta express {cuil, apellido_nombre, dni, nacimiento}
    producto_id: Mapped[str] = mapped_column(ForeignKey("pp_producto.id"))
    monto_solicitado: Mapped[Decimal] = mapped_column(Numeric(19, 4), default=0)
    plazo_solicitado: Mapped[int] = mapped_column(Integer, default=12)
    segmento: Mapped[str] = mapped_column(String(30), default="")
    canal: Mapped[str] = mapped_column(String(30), default="SUCURSAL")
    edad: Mapped[int | None] = mapped_column(Integer, nullable=True)
    antiguedad_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relacion: Mapped[str] = mapped_column(String(20), default="ESTANDAR")
    datos_adicionales: Mapped[dict] = mapped_column(JSON, default=dict)   # destino, cbu, observaciones
    origen: Mapped[str] = mapped_column(String(15), default="SUCURSAL")   # captación
    evaluacion: Mapped[dict] = mapped_column(JSON, default=dict)          # {elegible, motivos, tna_ofrecida, cuota_estimada}
    contrato_id: Mapped[str | None] = mapped_column(ForeignKey("pp_contrato.id"), nullable=True)
    motivo_rechazo: Mapped[str] = mapped_column(String(300), default="")
    creado_por: Mapped[str] = mapped_column(String(30), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    enviada_por: Mapped[str] = mapped_column(String(30), default="")
    resuelta_por: Mapped[str] = mapped_column(String(30), default="")   # aprobó/rechazó


class PPSolicitudDocumento(Base):
    """Documentación adjunta a una solicitud (DNI, recibo de sueldo…), subida por el ciudadano
    desde el portal. El asesor la ve/descarga en el backoffice al evaluar. Los bytes se guardan
    en la DB (self-contained); a escala real iría a object storage."""
    __tablename__ = "pp_solicitud_documento"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    solicitud_id: Mapped[str] = mapped_column(ForeignKey("pp_solicitud.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="OTRO")   # DNI_FRENTE, DNI_DORSO, RECIBO, OTRO
    nombre: Mapped[str] = mapped_column(String(200), default="")
    content_type: Mapped[str] = mapped_column(String(80), default="")
    tamano: Mapped[int] = mapped_column(Integer, default=0)
    contenido: Mapped[bytes] = mapped_column(LargeBinary)
    subido_por: Mapped[str] = mapped_column(String(40), default="")
    subido_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PPIdempotencia(Base):
    """Almacén de Idempotency-Key para altas mutantes. Si llega dos veces la misma clave (doble clic,
    retry de red), se devuelve la respuesta guardada en vez de repetir la operación."""
    __tablename__ = "pp_idempotencia"
    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(120), default="")
    usuario: Mapped[str] = mapped_column(String(30), default="")
    respuesta: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # None = reservada/en proceso
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PPWorkflowAprobacion(Base):
    """Aprobación registrada de un objeto concreto en un nivel de su regla (para ejecutar la cadena
    de N niveles en serie). objeto_id = id de la versión (LINEA), solicitud, o contrato.
    Unicidad (objeto, objeto_id, nivel_orden): un nivel se aprueba UNA sola vez — la DB es el árbitro
    contra la carrera de dos aprobadores concurrentes (evita el bypass de cuatro-ojos/N-ojos)."""
    __tablename__ = "pp_workflow_aprobacion"
    __table_args__ = (UniqueConstraint("objeto", "objeto_id", "nivel_orden", name="uq_wf_aprobacion_nivel"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    objeto: Mapped[str] = mapped_column(String(20), index=True)
    objeto_id: Mapped[str] = mapped_column(String(36), index=True)
    nivel_orden: Mapped[int] = mapped_column(Integer)
    aprobado_por: Mapped[str] = mapped_column(String(30))
    fecha: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PPWorkflowPendiente(Base):
    """Operación de contrato que espera aprobación (gate de workflow para DESEMBOLSO/REFINANCIACION).
    Cuando la regla del objeto está activa, la acción no ejecuta: crea este pendiente; al completar la
    cadena de aprobaciones se ejecuta la operación real."""
    __tablename__ = "pp_workflow_pendiente"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uid)
    objeto: Mapped[str] = mapped_column(String(20), index=True)   # DESEMBOLSO | REFINANCIACION
    contrato_id: Mapped[str] = mapped_column(ForeignKey("pp_contrato.id"), index=True)
    datos: Mapped[dict] = mapped_column(JSON, default=dict)       # p.ej. {tasa, plazo} en refi
    estado: Mapped[str] = mapped_column(String(15), default="PENDIENTE")  # PENDIENTE|APROBADO|RECHAZADO
    solicitado_por: Mapped[str] = mapped_column(String(30), default="")
    resuelto_por: Mapped[str] = mapped_column(String(30), default="")
    motivo: Mapped[str] = mapped_column(String(300), default="")
    creado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
