"""Esquemas Pydantic (v2) para la API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    """Respuesta paginada genérica."""
    total: int
    limit: int
    offset: int
    items: list[T]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    perfil: str
    nombre: str


# ---------- Cliente ----------
class ClienteBase(BaseModel):
    id_cliente: str = ""
    cuil: str
    dni: str = ""
    apellido_nombre: str = Field(min_length=1)
    sexo: str = ""
    fecha_nacimiento: date | None = None
    domicilio: str = ""
    barrio: str = ""
    localidad: str = ""
    telefono: str = ""
    email: str = ""
    cbu: str = ""
    debito_automatico: bool = False
    sueldo: Decimal = Field(default=Decimal("0"), ge=0)
    categoria_funcion: str = ""
    fecha_ingreso: date | None = None
    tipo_cliente: int = 0
    organismo_id: int | None = None


class ClientePerfilCrediticio(BaseModel):
    """Lo que sí es de Créditos. La identidad la edita el módulo Clientes (padrón único)."""
    sueldo: Decimal | None = None
    categoria_funcion: str | None = None
    fecha_ingreso: date | None = None
    tipo_cliente: int | None = None
    organismo_id: int | None = None
    debito_automatico: bool | None = None


class ClienteOut(ClienteBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    baja: bool
    fecha_baja: date | None = None
    motivo_baja: str = ""


# ---------- Línea ----------
class LineaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    cartera: int
    tipo_calculo: int
    tna: Decimal
    tasa_mora_diaria: Decimal
    iva: Decimal
    por_afecta: Decimal
    porcent_pp: Decimal
    seguro_pct: Decimal
    gastos_adm_pct: Decimal
    plazo_max: int
    monto_max: Decimal
    plazo_gracia: int
    paga_interes_gracia: bool
    suma_int_gracia_capital: bool
    admite_previo_pago: bool
    cta_contable: str
    activa: bool


# (El ABM de líneas usa LineaUpsertBase/LineaCreate/LineaAdminOut, más abajo.)


# ---------- Simulación de crédito ----------
class SimulacionRequest(BaseModel):
    linea_id: int
    capital: Decimal = Field(gt=0)
    plazo: int = Field(gt=0, le=240)
    fecha_primer_vencimiento: date
    cuota_fija: Decimal | None = None
    # datos del cliente para validar margen (opcional)
    sueldo: Decimal | None = None
    total_afectado: Decimal = Decimal("0")


class CuotaOut(BaseModel):
    numero: int
    vencimiento: str
    saldo_capital: str
    amortizacion: str
    interes: str
    iva_interes: str
    seguro: str
    iva_seguro: str
    gastos_adm: str
    iva_gastos_adm: str
    total: str


class SimulacionOut(BaseModel):
    linea: str
    tipo_calculo: int
    capital: Decimal
    cantidad_cuotas: int
    total_a_pagar: Decimal
    total_interes: Decimal
    cuota_promedio: Decimal
    margen_disponible: Decimal | None = None
    puede_tomar_credito: bool | None = None
    advertencias: list[str] = []
    cuotas: list[CuotaOut]


# ---------- Portal del ciudadano (Fase 1) ----------
class CiudadanoOut(BaseModel):
    sub: str
    email: str = ""
    nombre: str = ""


class PortalProductoOut(BaseModel):
    """Producto publicado del product builder (lo NUEVO), vista pública mínima."""
    id: str
    nombre: str
    codigo: str
    sistema: str
    tna: float
    monto_min: float
    monto_max: float
    plazo_min: int
    plazo_max: int


class DatosSolicitante(BaseModel):
    """Datos que el ciudadano declara (Fase 3) para evaluar elegibilidad/afectación.
    Rangos: antigüedad ≥0, sueldo >0 (H-146). Todos opcionales (None = no declarado).
    La edad no se pide: se calcula de `fecha_nacimiento` (H-219)."""
    segmento: str = ""            # relación laboral (AGENTE_PUBLICO, DOCENTE, JUBILADO…)
    fecha_nacimiento: date | None = None
    antiguedad_meses: int | None = Field(default=None, ge=0, le=1200)
    sueldo: float | None = Field(default=None, gt=0)   # sueldo neto declarado (para afectación estimada)


class PortalSimularIn(DatosSolicitante):
    producto_id: str
    monto: float = Field(gt=0)
    plazo: int = Field(gt=0, le=240)


class PortalCuotaOut(BaseModel):
    numero: int
    vencimiento: str
    capital: float
    interes: float
    cargos: float
    impuestos: float
    total: float


class PortalSimulacionOut(BaseModel):
    producto: str
    sistema: str
    tna: float
    monto: float
    cantidad_cuotas: int
    total_a_pagar: float
    total_interes: float
    cuota_promedio: float
    tea: float
    cft: float
    elegible: bool | None = None     # None = no declaró datos suficientes para evaluar
    motivos: list[str] = []
    afectacion: float | None = None  # % del sueldo declarado que representa la cuota
    cuotas: list[PortalCuotaOut]


class PortalHaberesOut(BaseModel):
    """Haberes del ciudadano traídos de la fuente (Mi Catamarca) o del mock."""
    disponible: bool = False
    sueldo: float | None = None
    antiguedad_meses: int | None = None
    segmento: str = ""
    empleador: str = ""
    fuente: str = ""   # "micatamarca" | "mock"


class PortalPreAprobadoIn(BaseModel):
    producto_id: str
    plazo: int = Field(gt=0, le=240)
    sueldo: float = Field(gt=0)
    afectacion_max: float = 30           # % del sueldo que puede ocupar la cuota


class PortalPreAprobadoOut(BaseModel):
    monto_maximo: float                  # 0 = ni el mínimo entra en el margen
    monto_min: float
    cuota: float
    afectacion: float
    plazo: int


class PortalVideoOut(BaseModel):
    id: str
    titulo: str
    url: str


class PortalSolicitudIn(DatosSolicitante):
    producto_id: str
    monto: float = Field(gt=0)
    plazo: int = Field(gt=0, le=240)
    # Datos personales que CARGA el ciudadano (H-162): Mi Catamarca sólo valida que la persona exista, no
    # devuelve su perfil, así que apellido/nombre/DNI los declara él (el DNI se necesita para liquidar).
    apellido: str = ""
    nombre: str = ""
    dni: str = ""
    haberes_fuente: str = "declarado"   # queda "declarado": el ciudadano declara sus haberes
    destino: str = ""                   # para qué es el crédito (VIVIENDA, VEHICULO, …)
    cbu: str = ""                       # CBU de acreditación (22 dígitos)
    acepta_terminos: bool = False       # consentimiento: términos y condiciones
    acepta_datos: bool = False          # consentimiento: tratamiento de datos personales
    email: str = ""                     # contacto declarado (puede diferir del de Mi Catamarca)
    telefono: str = ""                  # contacto declarado
    videos_vistos: list[str] = []       # ids de los videos obligatorios que vio completos (paso 4)


class PortalSolicitudOut(BaseModel):
    numero: str
    estado: str
    producto: str
    monto: float
    plazo: int
    cuota_estimada: float
    tna: float
    fecha: str
    motivo_rechazo: str = ""


# ---------- Portal · Mis créditos (préstamo otorgado + cuotas + notificaciones) ----------
class PortalProximaCuota(BaseModel):
    numero: int
    vencimiento: str
    total: float
    vencida: bool = False


class PortalCreditoOut(BaseModel):
    contrato: str
    producto: str
    monto: float
    saldo: float
    estado: str
    tna: float = 0
    plazo: int
    cuotas_pagadas: int
    cuotas_total: int
    progreso: float           # % de cuotas pagadas
    en_mora: bool = False
    proxima: PortalProximaCuota | None = None


class PortalCuotaEstadoOut(BaseModel):
    numero: int
    vencimiento: str
    total: float
    pagado: float
    estado: str               # PENDIENTE | PAGADA
    vencida: bool


class PortalCreditoDetalle(PortalCreditoOut):
    fecha_alta: str = ""
    cuotas: list[PortalCuotaEstadoOut] = []


class PortalNotificacionOut(BaseModel):
    tipo: str                 # otorgado | vencimiento | mora | pago
    titulo: str
    detalle: str
    fecha: str
    contrato: str = ""


class PortalSolicitudDetalle(PortalSolicitudOut):
    sistema: str = ""
    destino: str = ""
    segmento: str = ""
    fecha_nacimiento: str | None = None
    edad: int | None = None
    antiguedad_meses: int | None = None
    sueldo: float | None = None
    afectacion: float | None = None
    total_a_pagar: float = 0
    cuotas: list[PortalCuotaOut] = []


# ---------- Solicitudes ----------
class SolicitudCreate(BaseModel):
    cliente_id: int
    linea_id: int
    monto_solicitado: Decimal = Field(gt=0)
    cantidad_cuotas: int = Field(gt=0, le=240)
    fecha_primer_vencimiento: date
    cuota_fija: Decimal | None = None
    garante1_cuil: str = ""
    garante2_cuil: str = ""
    garante3_cuil: str = ""
    garante4_cuil: str = ""
    # conceptos reales (opcionales)
    gastos_originacion: Decimal = Decimal("0")
    iva_gastos_originacion: Decimal = Decimal("0")
    quebranto: Decimal = Decimal("0")
    iva_quebranto: Decimal = Decimal("0")
    cft: Decimal = Decimal("0")
    credito_previo_pago: int | None = None
    importe_previo_pago: Decimal = Decimal("0")
    observaciones: str = ""


class SolicitudOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cliente_id: int
    linea_id: int
    estado: str
    fecha_solicitud: date
    monto_solicitado: Decimal
    cantidad_cuotas: int
    cuota_fija: Decimal
    garante1_cuil: str
    observaciones: str


class SolicitudDetalle(SolicitudOut):
    cliente_nombre: str
    linea_nombre: str
    margen_disponible: Decimal | None = None
    puede_otorgarse: bool
    advertencias: list[str] = []
    credito_id: int | None = None


class CuotaCreditoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    numero: int
    fecha_vencimiento: date
    saldo_capital: Decimal
    amortizacion: Decimal
    interes: Decimal
    iva_interes: Decimal
    seguro: Decimal
    gastos_adm: Decimal
    total: Decimal
    estado: str


class CreditoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    solicitud_id: int | None = None   # los créditos migrados del ETL no tienen solicitud
    linea_id: int | None = None
    cliente_id: int
    capital: Decimal
    saldo_capital: Decimal
    fecha_otorgamiento: date | None
    estado: str


class CreditoDetalle(CreditoOut):
    cliente_nombre: str
    cantidad_cuotas: int
    total_a_pagar: Decimal
    cuotas: list[CuotaCreditoOut]


class PagoCuotaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cuota_id: int
    capital: Decimal
    interes: Decimal
    iva_interes: Decimal
    seguro: Decimal
    gastos_adm: Decimal
    interes_punitorio: Decimal
    iva_punitorio: Decimal
    dias_mora: int
    total_pagado: Decimal


class ReciboOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    fecha_pago: date
    cliente_id: int
    credito_id: int
    cajero: str
    via_pago: str
    total: Decimal
    estado: str


class ReciboDetalle(ReciboOut):
    cliente_nombre: str
    pagos: list[PagoCuotaOut]


class CancelacionCuotaItem(BaseModel):
    cuota: int
    vencida: bool
    capital: Decimal
    interes: Decimal
    iva: Decimal
    punitorio: Decimal
    iva_punit: Decimal
    subtotal: Decimal


class CancelacionDetalle(BaseModel):
    credito_id: int
    cantidad_cuotas: int
    capital: Decimal
    interes: Decimal
    iva: Decimal
    punitorio: Decimal
    iva_punit: Decimal
    total: Decimal
    items: list[CancelacionCuotaItem]


class CancelacionRequest(BaseModel):
    fecha_pago: date
    via_pago: str = "EFECTIVO"


class BajaCreditoRequest(BaseModel):
    motivo: str = Field(min_length=1)
    fecha: date | None = None


class RecalculoCuotaItem(BaseModel):
    numero: int
    fecha_vto: date | None
    capital: Decimal
    interes: Decimal
    iva: Decimal
    total: Decimal


class RecalculoPreview(BaseModel):
    credito_id: int
    modo: str
    cantidad_actual: int
    cantidad_propuesta: int
    total_actual: Decimal
    total_propuesto: Decimal
    actual: list[RecalculoCuotaItem]
    propuesto: list[RecalculoCuotaItem]


class RecalculoRequest(BaseModel):
    modo: str = Field(description="vencimientos | jubilatorio")
    primer_vto: date | None = None
    haber: Decimal | None = None


# ---------- Turnos de crédito (32065/67/68) ----------
class TurnoDistItem(BaseModel):
    fecha: date
    cantidad: int


class TurnosPreview(BaseModel):
    periodo: str
    grupo: str
    dias_habiles: int
    turnos_por_dia: int
    resto: int
    total: int
    ya_existen: int
    distribucion: list[TurnoDistItem]


class TurnosGenerarRequest(BaseModel):
    periodo: str = Field(min_length=6, max_length=6)
    cantidad: int = Field(gt=0)
    grupo: str = "TODO"
    desde: date | None = None


class TurnoAsignarRequest(BaseModel):
    periodo: str = Field(min_length=6, max_length=6)
    cuil: str = Field(min_length=1)
    apellido_nombre: str = ""
    linea: int = 0
    sueldo: Decimal | None = None
    numero: int | None = None    # para turno excepcional (32068)


class TurnoCreditoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo: str
    numero: int
    periodo: str
    fecha: date | None
    cuil: str
    apellido_nombre: str
    linea: int
    sueldo: Decimal
    usado: bool
    autorizado: bool


# ---------- Consultas / informes de Créditos ----------
class CreditoResumen(BaseModel):
    id: int
    capital: Decimal
    saldo_capital: Decimal
    estado: str
    linea: str
    cuotas_pendientes: int
    proxima_cuota_vto: date | None
    proxima_cuota_importe: Decimal | None


class SituacionCliente(BaseModel):
    cliente_id: int
    apellido_nombre: str
    cuil: str
    sueldo: Decimal
    cbu: str
    por_afecta: Decimal | None = None
    total_afectado: Decimal
    margen_disponible: Decimal | None
    creditos_activos: int
    saldo_total: Decimal
    creditos: list[CreditoResumen]


class LineaEstadistica(BaseModel):
    linea_id: int
    linea: str
    cartera: int
    cantidad: int
    capital_otorgado: Decimal
    saldo: Decimal


class EstadisticasCartera(BaseModel):
    creditos_activos: int
    creditos_cancelados: int
    capital_otorgado_total: Decimal
    saldo_total: Decimal
    por_linea: list[LineaEstadistica]


class EnvioItem(BaseModel):
    credito_id: int
    cliente: str
    cuil: str
    cbu: str
    cuota_numero: int
    vencimiento: date
    importe: Decimal


class EnviosResumen(BaseModel):
    desde: date
    hasta: date
    cantidad: int
    total: Decimal
    items: list[EnvioItem]


# ---------- Utilidades / Tablas (ABMs) ----------
class LineaUpsertBase(BaseModel):
    nombre: str
    cartera: int
    tipo_calculo: int = 1
    tna: Decimal = Decimal("0")
    tasa_mora_diaria: Decimal = Decimal("0")
    iva: Decimal = Decimal("21")
    por_afecta: Decimal = Decimal("30")
    porcent_pp: Decimal = Decimal("0")
    seguro_pct: Decimal = Decimal("0")
    gastos_adm_pct: Decimal = Decimal("0")
    plazo_max: int = 60
    monto_max: Decimal = Decimal("0")
    plazo_gracia: int = 0
    paga_interes_gracia: bool = False
    suma_int_gracia_capital: bool = False
    admite_previo_pago: bool = False
    cta_contable: str = ""
    compania_seguros_id: int | None = None
    activa: bool = True


class LineaCreate(LineaUpsertBase):
    pass


class LineaAdminOut(LineaUpsertBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OrganismoUpsert(BaseModel):
    codigo: str
    nombre: str
    activo: bool = True


class OrganismoAdminOut(OrganismoUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ParametroUpsert(BaseModel):
    clave: str
    valor: str
    descripcion: str = ""
    ambito: str = "general"   # general|creditos|contabilidad (H-197)


class ParametroOut(ParametroUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TurnoResumen(BaseModel):
    id: int
    numero: int
    tipo: str
    cliente: str
    estado: str
    box: str


class Tablero(BaseModel):
    fecha: date
    en_espera: list[TurnoResumen]
    llamados: list[TurnoResumen]
    atendidos: int
    cancelados: int


# ---------- Reportería operativa ----------
class PendienteItem(BaseModel):
    credito_id: int
    cliente: str
    cuil: str
    cuota_numero: int
    vencimiento: date
    dias_mora: int
    importe_cuota: Decimal
    mora: Decimal
    total: Decimal


class PendientesCobro(BaseModel):
    fecha_corte: date
    cantidad: int
    total_cuota: Decimal
    total_mora: Decimal
    total: Decimal
    items: list[PendienteItem]
