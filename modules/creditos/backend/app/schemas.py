"""Esquemas Pydantic (v2) para la API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class LoginRequest(BaseModel):
    username: str
    password: str


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


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    apellido_nombre: str | None = None
    dni: str | None = None
    sexo: str | None = None
    fecha_nacimiento: date | None = None
    domicilio: str | None = None
    barrio: str | None = None
    localidad: str | None = None
    telefono: str | None = None
    email: str | None = None
    cbu: str | None = None
    debito_automatico: bool | None = None
    sueldo: Decimal | None = None
    categoria_funcion: str | None = None
    fecha_ingreso: date | None = None
    tipo_cliente: int | None = None
    organismo_id: int | None = None


class ClienteBaja(BaseModel):
    motivo: str


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
    Rangos: edad 18-99, antigüedad ≥0, sueldo >0 (H-146). Todos opcionales (None = no declarado)."""
    segmento: str = ""            # relación laboral (AGENTE_PUBLICO, DOCENTE, JUBILADO…)
    edad: int | None = Field(default=None, ge=18, le=99)
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


# ---------- Caja / cobranza ----------
class CuotaPendienteOut(BaseModel):
    cuota_id: int
    numero: int
    fecha_vencimiento: date
    importe_cuota: Decimal
    ya_pagado: Decimal
    dias_mora: int
    interes_punitorio: Decimal
    iva_punitorio: Decimal
    total_a_pagar: Decimal


class CobranzaRequest(BaseModel):
    credito_id: int
    cuotas: list[int] = Field(min_length=1, description="Números de cuota a cobrar")
    fecha_pago: date
    via_pago: str = "EFECTIVO"


# ---------- Cola de caja por persona (22515) ----------
class ColaItem(BaseModel):
    origen: str
    f_alta: date | None
    dni: str
    cuil: str
    apellido_nombre: str
    cliente_id: int
    credito_id: int
    cuota: int
    importe: Decimal
    interes: Decimal
    iva: Decimal
    dias_mora: int
    total: Decimal


class ColaClienteResumen(BaseModel):
    cliente_id: int
    cuil: str
    dni: str
    apellido_nombre: str
    total: Decimal


class ColaCaja(BaseModel):
    clientes: list[ColaClienteResumen]
    items: list[ColaItem]
    total: Decimal
    cantidad: int


class ColaCobroCredito(BaseModel):
    credito_id: int
    cuotas: list[int] = Field(min_length=1)


class ColaCobroRequest(BaseModel):
    items: list[ColaCobroCredito] = Field(min_length=1)
    fecha_pago: date
    via_pago: str = "EFECTIVO"


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


# ---------- Contabilidad ----------
class AsientoLineaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cuenta_codigo: str
    cuenta_nombre: str
    debe: Decimal
    haber: Decimal
    centro_codigo: str = ""


class AsientoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: date
    concepto: str
    origen: str
    ref_id: int | None
    numero: int | None = None
    reversado: bool = False
    reversa_de: int | None = None
    usuario: str = ""
    estado: str = "publicado"
    diario_codigo: str = ""
    lineas: list[AsientoLineaOut]


class AsientoLineaIn(BaseModel):
    cuenta_codigo: str = ""
    debe: Decimal = Decimal("0")
    haber: Decimal = Decimal("0")
    centro_codigo: str = ""


class AsientoManualIn(BaseModel):
    fecha: date | None = None
    concepto: str = Field(min_length=1, max_length=120)
    diario_codigo: str = "VAR"
    lineas: list[AsientoLineaIn] = []


class ImputacionIn(BaseModel):
    cuenta_codigo: str = Field(min_length=1, max_length=12)


class EjercicioIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=40)
    fecha_desde: date
    fecha_hasta: date


class CentroCostoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=12)
    nombre: str = Field(min_length=1, max_length=60)
    activo: bool = True


# ---------- Plan de cuentas ----------
class EntidadRelacionada(BaseModel):
    tipo: str = ""
    entidad: str = ""


class CuentaContableIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=12)
    nombre: str = Field(min_length=1, max_length=80)
    tipo: str = "activo"   # rubro: activo | pasivo | patrimonio | ingreso | egreso
    descripcion: str = ""
    alias: str = ""
    moneda: str = "ARS"
    clasificacion: str = "Sin clasificar"   # Caja | Banco | Cliente | Proveedor | Impuesto | Resultado…
    saldo_normal: str = "deudor"            # deudor | acreedor
    imputable: bool = True
    manual: bool = False
    entidades: list[EntidadRelacionada] = []

    @field_validator("codigo", "nombre")
    @classmethod
    def _no_vacio(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("Campo obligatorio")
        return v.strip()


class CuentaContableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: str
    nombre: str
    tipo: str
    descripcion: str = ""
    alias: str = ""
    moneda: str = "ARS"
    clasificacion: str = "Sin clasificar"
    saldo_normal: str = "deudor"
    imputable: bool = True
    manual: bool = False
    entidades: list[EntidadRelacionada] = []
    en_uso: bool = False   # tiene asientos que la referencian (no se puede borrar)
    base: bool = False     # forma parte de la plantilla base (usada por el motor de asientos)


# ---------- Cierre de caja ----------
class ConceptoCierre(BaseModel):
    concepto: str
    importe: Decimal


class CobranzaPeriodoItem(BaseModel):
    origen: str
    denominacion: str
    nombres: str
    dni: str
    no_recibo: int
    fecha_pago: date | None
    via_pago: str
    cajero: str
    total: Decimal


class ReciboDiaItem(BaseModel):
    no_recibo: int
    cod_agencia: int
    titular: str
    origen: str
    fecha_pago: date | None
    importe: Decimal
    cajero: str


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


class RecibosDelDia(BaseModel):
    fecha: date
    cantidad: int
    total: Decimal
    items: list[ReciboDiaItem]


class PagoRealizadoItem(BaseModel):
    origen: str
    coding: int
    subing: int
    no_credito: int
    cuil: str
    dni: str
    apellido_nombre: str
    cuota: int
    no_recibo: int
    cajero: str
    moneda: str
    fecha_pago: date | None
    total: Decimal


class PagosRealizados(BaseModel):
    desde: date
    hasta: date
    cantidad: int
    total: Decimal
    truncado: bool
    items: list[PagoRealizadoItem]


class PlanillaContableCreditos(BaseModel):
    fecha: date
    cantidad: int
    conceptos: list[ConceptoCierre]
    total: Decimal


class InteresIvaItem(BaseModel):
    origen: str
    cantidad: int
    interes: Decimal
    iva_interes: Decimal
    interes_punit: Decimal
    iva_punit: Decimal
    total_interes: Decimal
    total_iva: Decimal


class InteresesIvaMensual(BaseModel):
    mes: int
    anio: int
    items: list[InteresIvaItem]
    total_interes: Decimal
    total_iva: Decimal
    total: Decimal


class RecaudacionOrigen(BaseModel):
    origen: str
    meses: list[Decimal]         # 12 valores (ene..dic)
    premios: list[Decimal]
    total: Decimal
    premios_total: Decimal


class RecaudacionAnual(BaseModel):
    anio: int
    origenes: list[RecaudacionOrigen]
    total_general: Decimal


class CobranzasPeriodo(BaseModel):
    desde: date
    hasta: date
    cantidad: int
    total_creditos: Decimal
    total_quiniela: Decimal
    total: Decimal
    items: list[CobranzaPeriodoItem]


class CierreCaja(BaseModel):
    fecha: date
    cajero: str | None
    cantidad_recibos: int
    total_cobrado: Decimal
    por_via_pago: list[ConceptoCierre]
    por_concepto: list[ConceptoCierre]
    por_moneda: list[ConceptoCierre] = []       # c_cierremoneda (pesos/bonos)
    quiniela_cantidad: int = 0
    quiniela_cobrado: Decimal = Decimal("0")


# ---------- Seguros ----------
class PolizaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    credito_id: int
    cliente_id: int
    compania_id: int
    capital_asegurado: Decimal
    fecha_alta: date
    estado: str


class LiquidacionSeguroItem(BaseModel):
    compania_id: int
    compania: str
    cantidad_recibos: int
    total_seguro: Decimal


class SegurosCobradosDia(BaseModel):
    fecha: date
    recibos: int
    seguro: Decimal


class SegurosCobrados(BaseModel):
    desde: date
    hasta: date
    total_seguro: Decimal
    dias: list[SegurosCobradosDia]


class PrimasDevengadas(BaseModel):
    desde: date
    hasta: date
    devengado: Decimal
    cobrado: Decimal
    pendiente: Decimal


class PagoSeguroItem(BaseModel):
    numero: int
    fecha: date
    beneficiario: str
    concepto: str
    importe: Decimal
    estado: str


class PagosSeguros(BaseModel):
    desde: date
    hasta: date
    cantidad: int
    total: Decimal
    items: list[PagoSeguroItem]


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


# ---------- Tesorería / Egresos ----------
class OrdenPagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    fecha: date
    beneficiario: str
    cuit_beneficiario: str
    concepto: str
    tipo: str
    importe: Decimal
    estado: str
    banco: str
    cheque_numero: str
    fecha_pago: date | None
    credito_id: int | None


class AutorizacionOPOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nop: int
    fecha: date | None
    vigencia: date | None
    importe: Decimal
    importe_usado: Decimal
    saldo: Decimal
    sistema: str
    habilitada: bool
    cancelada: bool
    anulada: bool
    nres1: int
    fres1: date | None


class ConsumirCupoRequest(BaseModel):
    importe: Decimal = Field(gt=0)
    fecha: date | None = None
    sistema: str | None = None


class AutorizacionOPUpsert(BaseModel):
    nop: int = 0
    fecha: date | None = None
    vigencia: date | None = None
    importe: Decimal = Decimal("0")
    sistema: str = ""
    habilitada: bool = True
    nres1: int = 0
    fres1: date | None = None
    nres2: int = 0
    fres2: date | None = None


class OrdenPagoCreate(BaseModel):
    beneficiario: str
    concepto: str
    importe: Decimal = Field(gt=0)
    tipo: str = "PROVEEDOR"
    cuit: str = ""
    fecha: date | None = None


class PagoOrdenRequest(BaseModel):
    banco: str
    cheque_numero: str
    fecha_pago: date | None = None


class TotalesEgresos(BaseModel):
    pendiente: Decimal
    girado: Decimal


class ReporteOPFila(BaseModel):
    tipo: str
    cantidad: int
    pendiente: Decimal
    girado: Decimal
    anulado: Decimal
    importe: Decimal


class ReporteOP(BaseModel):
    por_tipo: list[ReporteOPFila]
    total: ReporteOPFila


class ChequeraCreate(BaseModel):
    banco: str
    cuenta: str = ""
    desde: int = Field(gt=0)
    hasta: int = Field(gt=0)


class ChequeraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    banco: str
    cuenta: str
    numero_desde: int
    numero_hasta: int
    proximo: int
    activa: bool


class PagoConChequera(BaseModel):
    chequera_id: int
    fecha_pago: date | None = None


class OpRevisionItem(BaseModel):
    numero: int
    fecha: date
    beneficiario: str
    concepto: str
    importe: Decimal
    tipo: str


class RevisionEgresos(BaseModel):
    pendientes: list[OpRevisionItem]
    incompletas: list[OpRevisionItem]
    total_pendiente: Decimal


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


class ProveedorUpsert(BaseModel):
    cuit: str = ""
    razon_social: str
    contacto: str = ""
    domicilio: str = ""
    localidad: str = ""
    departamento: str = ""
    tipo_iva: str = ""
    ingresos_brutos: str = ""
    anulado: bool = False


class ProveedorOut(ProveedorUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CompaniaUpsert(BaseModel):
    nombre: str
    cuit: str = ""
    activa: bool = True


class CompaniaOut(CompaniaUpsert):
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


class RequisitoUpsert(BaseModel):
    linea_id: int | None = None
    descripcion: str
    obligatorio: bool = True


class RequisitoOut(RequisitoUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int


class GasistaUpsert(BaseModel):
    nombre: str
    matricula: str = ""
    cuit: str = ""
    activo: bool = True


class GasistaOut(GasistaUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int


class MontoPeriodoUpsert(BaseModel):
    linea_id: int
    periodo: str
    monto_maximo: Decimal


class MontoPeriodoOut(MontoPeriodoUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: int


class UsuarioCreate(BaseModel):
    username: str
    nombre: str = ""
    password: str
    perfil: str = "XCR"


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    nombre: str
    perfil: str
    activo: bool


class CambioClave(BaseModel):
    password: str


# ---------- Despacho ----------
class ModeloResolucionIn(BaseModel):
    descripcion: str = Field(min_length=1)  # obligatoria; se rechaza si queda vacía al recortar (validator)
    tipo: str = "RES"            # RES / DIS
    plantilla: str = ""          # HTML del editor mini-Word (texto base)
    seguros: bool = False

    @field_validator("descripcion")
    @classmethod
    def _desc_no_vacia(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("La descripción es obligatoria")
        return v


class BeneficiarioIn(BaseModel):
    tipo_doc: int = 0
    nro_doc: str = ""
    nombre: str = Field(min_length=1)
    tipo_bene: int = 0


class BeneficiarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_doc: int
    nro_doc: str
    nombre: str
    tipo_bene: int


class ResolucionCreate(BaseModel):
    tipo: str = "RES"          # RES / DIS
    asunto: str = ""
    texto: str = ""
    organo: str = ""
    fecha: date | None = None
    modelo_id: int | None = None       # "Modelo a utilizar" (id único; su descripción es el motivo)
    modelo_codigo: int | None = None   # compat: COD_MOD (si no viene modelo_id)
    importe: Decimal = Field(default=Decimal("0"), ge=0)
    origen: str = ""                   # Exp./Nota que origina el instrumento legal
    beneficiarios: list[BeneficiarioIn] = []


class ResolucionUpdate(BaseModel):
    """Edición de un BORRADOR (no cambia tipo/número/año). Sólo mientras no sea oficial."""
    fecha: date | None = None
    modelo_id: int | None = None
    modelo_codigo: int | None = None
    texto: str = ""
    importe: Decimal = Field(default=Decimal("0"), ge=0)
    origen: str = ""
    beneficiarios: list[BeneficiarioIn] = []


class NumeroRealIn(BaseModel):
    fecha_real: date | None = None     # "Carga Nº Real": el sistema asigna el próximo por tipo+año


class AnexoAsignar(BaseModel):
    tipo: int = 6
    numero: int              # N° correlativo de la resolución
    fecha: date
    solicitud_ids: list[int]


class ResolucionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    anio: int
    tipo: str
    fecha: date
    numero_real: int | None = None
    fecha_real: date | None = None
    organo: str
    asunto: str
    motivo_cod: int = 0
    motivo: str = ""
    importe: Decimal = Decimal("0")
    modelo_codigo: int | None = None
    origen: str = ""
    nro_op: int | None = None
    texto: str
    estado: str
    anulada: bool = False


class ResolucionDetalle(ResolucionOut):
    beneficiarios: list[BeneficiarioOut] = []


class ExpedienteCreate(BaseModel):
    numero: str
    caratula: str
    iniciador: str = ""
    oficina_inicial: str
    fecha: date | None = None


class PaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    orden: int
    fecha: date
    oficina_origen: str
    oficina_destino: str
    motivo: str
    usuario: str


class ExpedienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: str
    caratula: str
    iniciador: str
    fecha_inicio: date
    estado: str
    oficina_actual: str


class ExpedienteDetalle(ExpedienteOut):
    pases: list[PaseOut]


class PaseRequest(BaseModel):
    oficina_destino: str
    motivo: str = ""
    fecha: date | None = None


# ---------- Mesa de entradas ----------
class TipoTramiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    prefijo: str
    activo: bool


class TurnoCreate(BaseModel):
    tipo_tramite_id: int
    cliente_nombre: str = ""
    cliente_cuil: str = ""
    fecha: date | None = None


class TurnoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    fecha: date
    tipo_tramite_id: int
    cliente_nombre: str
    cliente_cuil: str
    estado: str
    box: str


class LlamarRequest(BaseModel):
    box: str
    tipo_tramite_id: int | None = None
    fecha: date | None = None


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


# ---------- Regímenes especiales de Seguros ----------
class RegimenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    tipo: str
    monto_default: Decimal
    activo: bool


class BeneficiarioCreate(BaseModel):
    apellido_nombre: str
    cuil: str = ""
    dni: str = ""
    cbu: str = ""
    monto_mensual: Decimal | None = None
    numero_resolucion: str = ""
    fecha_alta: date | None = None


class BeneficiarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    regimen_id: int
    apellido_nombre: str
    cuil: str
    dni: str
    cbu: str
    monto_mensual: Decimal
    numero_resolucion: str
    fecha_alta: date
    estado: str


class CuotaRegimenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    beneficiario_id: int
    periodo: str
    monto: Decimal
    estado: str
    orden_pago_id: int | None


class GeneracionCuotasOut(BaseModel):
    regimen: str
    periodo: str
    cuotas_generadas: int
    ordenes_pago: int
    total: Decimal
    beneficiarios_vigentes: int


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


class IvaPeriodo(BaseModel):
    desde: date
    hasta: date
    iva_debito: Decimal
    cantidad_asientos: int


class OpDevengadaTipo(BaseModel):
    tipo: str
    cantidad: int
    total: Decimal


class OpDevengadas(BaseModel):
    desde: date
    hasta: date
    cantidad: int
    total: Decimal
    por_tipo: list[OpDevengadaTipo]


class SolicitudBaja(BaseModel):
    solicitud_id: int
    cliente: str
    cuil: str
    monto: Decimal
    fecha: date
    observaciones: str


class ReciboControl(BaseModel):
    numero: int
    cliente: str
    via_pago: str
    total: Decimal


class CajeroControl(BaseModel):
    cajero: str
    cantidad: int
    subtotal: Decimal
    recibos: list[ReciboControl]


class ControlCaja(BaseModel):
    fecha: date
    cajeros: list[CajeroControl]
    cantidad_total: int
    total_general: Decimal


# ---------- Juegos / Quiniela ----------
class AgenciaJuegoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    numero: int
    subagencia: int
    interior: bool
    quiniela: bool
    quini6: bool
    loto: bool
    brinco: bool
    prode: bool
    telekino: bool
    activa: bool


class LiquidacionAgenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    no_agencia: int
    subagencia: int
    juego: str
    no_sorteo: int
    fecha_sorteo: date | None
    recaudacion: Decimal
    premios: Decimal
    comision_agencia: Decimal
    multas: Decimal
    total: Decimal
    pagado: bool
    no_recibo: int


class ResumenJuegos(BaseModel):
    cantidad: int
    recaudacion: Decimal
    premios: Decimal
    comisiones: Decimal
    multas: Decimal
    total: Decimal


class JuegoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    codigo: int
    modalidad: int
    cod_afip: int
    denominacion: str
    com_agencia: Decimal
    com_subagencia: Decimal


# ---------- Aplicativo de caja de quiniela (22505) ----------
class DeudaAgenciaItem(BaseModel):
    id: int
    cod_juego: int
    juego: str
    no_sorteo: int
    fecha_sorteo: date | None
    no_agencia: int
    subagencia: int
    moneda: str
    total: Decimal
    intereses: Decimal
    iva: Decimal
    total_gral: Decimal
    fecha_vto: date | None


class DeudaAgencia(BaseModel):
    cod_agencia: int
    cantidad: int
    bonos: Decimal
    pesos: Decimal
    total: Decimal
    items: list[DeudaAgenciaItem]


class FormaPago(BaseModel):
    moneda: str = "$"       # 'B' bonos / '$' pesos
    importe: Decimal
    cheque: str = ""


class CobroAgenciaRequest(BaseModel):
    cod_agencia: int
    formas_pago: list[FormaPago] = Field(min_length=1)
    premios_bonos: Decimal = Decimal("0")
    premios_pesos: Decimal = Decimal("0")
    fecha: date | None = None


class DeudaAgenciaInformeItem(BaseModel):
    cod_agencia: int
    no_agencia: int
    subagencia: int
    cod_juego: int
    juego: str
    no_sorteo: int
    fecha_sorteo: date | None
    moneda: str
    total: Decimal
    intereses: Decimal
    iva: Decimal
    total_gral: Decimal
    fecha_vto: date | None
    dias_atraso: int


class DeudaAgenciaInforme(BaseModel):
    cod_agencia: int | None
    cantidad: int
    total: Decimal
    items: list[DeudaAgenciaInformeItem]


class LiqCobradaItem(BaseModel):
    cajero: str
    no_recibo: int
    cod_agencia: int
    cod_juego: int
    juego: str
    no_sorteo: int
    moneda: str
    total_gral: Decimal


class LiqCobradaResumen(BaseModel):
    cajero: str
    cantidad: int
    total: Decimal


class LiquidacionesCobradas(BaseModel):
    fecha: date
    cantidad: int
    total: Decimal
    resumen: list[LiqCobradaResumen]
    items: list[LiqCobradaItem]


class CompensacionItem(BaseModel):
    cod_agencia: int
    no_agencia: int
    subagencia: int
    total: Decimal
    premios: Decimal
    com_premios: Decimal
    total_gral: Decimal


class CompensacionGrupo(BaseModel):
    grupo: str
    cantidad: int
    total_gral: Decimal
    items: list[CompensacionItem]


class PremiosCompensados(BaseModel):
    fecha_vto: date
    grupos: list[CompensacionGrupo]
    total_general: Decimal


class ChequeAgenciaItem(BaseModel):
    cod_agencia: int
    premios: Decimal
    total: Decimal
    intereses: Decimal
    iva: Decimal
    neto: Decimal
    cheque: Decimal


class ChequesAgencias(BaseModel):
    fecha_vto: date
    cantidad: int
    total_cheques: Decimal
    items: list[ChequeAgenciaItem]


class PremioQuinielaItem(BaseModel):
    cajero: str
    no_recibo: int
    cod_agencia: int
    no_agencia: int
    subagencia: int
    cod_juego: int
    juego: str
    no_sorteo: int
    moneda: str
    premio: Decimal


class PremiosQuiniela(BaseModel):
    fecha: date
    modo: str
    cantidad: int
    total: Decimal
    resumen: list[LiqCobradaResumen]
    items: list[PremioQuinielaItem]


class IngresosBrutosItem(BaseModel):
    cod_agencia: int
    no_agencia: int
    subagencia: int
    cantidad: int
    recaudacion: Decimal
    comisiones: Decimal
    ing_brutos: Decimal


class IngresosBrutosPeriodo(BaseModel):
    mes: int
    anio: int
    cantidad_agencias: int
    total_recaudacion: Decimal
    total_comisiones: Decimal
    total_ing_brutos: Decimal
    items: list[IngresosBrutosItem]


class CajaPagoAgenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cod_agencia: int
    fecha_pago: date | None
    no_recibo: int
    bonos: Decimal
    pesos: Decimal
    total: Decimal
    cobrado_bonos: Decimal
    cobrado_pesos: Decimal
    cobrado_total: Decimal
    vuelto_bonos: Decimal
    vuelto_pesos: Decimal
    premios_bonos: Decimal
    premios_pesos: Decimal
    cajero: str
    anulado: bool


class ResumenSeguroAdicional(BaseModel):
    periodo: str
    agentes: int
    con_adicional: int
    sin_adicional: int
    total_obligatorio: Decimal
    total_sepelio: Decimal
    total_conyuge: Decimal
    total_adicional: Decimal


class SeguroAgenteOut(BaseModel):
    cuil: str
    titular: str
    remuneracion: Decimal
    seg_obligatorio: Decimal
    seg_sepelio: Decimal
    seg_conyuge: Decimal
    seg_adicional: Decimal


class SorteoOut(BaseModel):
    id: int
    cod_juego: int
    juego: str
    no_sorteo: int
    fecha_sorteo: date | None
    fecha_vto: date | None
    importado_caja: bool


class IngresoJuegoOut(BaseModel):
    juego: str
    cantidad: int
    recaudacion: Decimal
    premios: Decimal
    comisiones: Decimal
    neto: Decimal
    total: Decimal
