from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- modelos
class ModeloIn(BaseModel):
    descripcion: str
    tipo: str = "RES"
    serie: int | None = None            # área que emite (VFP: TIPO_RES); 1 si no se indica
    codigo: int | None = None           # se autoasigna (MAX+1) si no viene
    es_seguros: bool | None = False
    plantilla: str | None = ""
    activo: bool | None = None


class ModeloOut(BaseModel):
    id: int
    codigo: int
    serie: int
    serie_nombre: str
    descripcion: str
    tipo: str
    es_seguros: bool
    plantilla: str
    tiene_plantilla: bool
    activo: bool

    model_config = {"from_attributes": True}


# --------------------------------------------------------------------------- resoluciones
class BeneficiarioIn(BaseModel):
    tipo_doc: int = 0
    nro_doc: str = ""
    nombre: str = ""
    tipo_bene: int = 0
    importe: Decimal = Decimal("0")


class BeneficiarioOut(BeneficiarioIn):
    id: int

    model_config = {"from_attributes": True}


class ResolucionIn(BaseModel):
    tipo: str = "RES"
    serie: int | None = None            # si viene un modelo, manda la serie del modelo
    fecha: date | None = None
    asunto: str | None = None
    organo: str | None = None
    modelo_id: int | None = None
    importe: Decimal | None = None
    origen: str | None = None
    nro_op: int | None = None
    texto: str | None = None
    beneficiarios: list[BeneficiarioIn] | None = None


class ResolucionUpdate(BaseModel):
    fecha: date | None = None
    asunto: str | None = None
    organo: str | None = None
    modelo_id: int | None = None
    importe: Decimal | None = None
    origen: str | None = None
    nro_op: int | None = None
    texto: str | None = None
    beneficiarios: list[BeneficiarioIn] | None = None


class NumeroRealIn(BaseModel):
    fecha_real: date | None = None


class AnulacionIn(BaseModel):
    motivo: str


class ResolucionOut(BaseModel):
    id: int
    numero: int
    anio: int
    tipo: str
    serie: int
    serie_nombre: str
    fecha: date
    numero_real: int | None
    fecha_real: date | None
    organo: str
    asunto: str
    motivo: str
    motivo_codigo: int
    importe: Decimal
    modelo_id: int | None
    origen: str
    nro_op: int | None
    estado: str
    anulada: bool
    motivo_anulacion: str
    creado_por: str
    creado_en: datetime | None

    model_config = {"from_attributes": True}


class ResolucionDetalle(ResolucionOut):
    texto: str
    beneficiarios: list[BeneficiarioOut] = []


class PaginaResoluciones(BaseModel):
    items: list[ResolucionOut]
    total: int
    pagina: int
    por_pagina: int


# --------------------------------------------------------------------------- anexo
class SolicitudAnexoOut(BaseModel):
    id: int
    fecha_solicitud: date | None
    cuil: str
    apellido_nombre: str
    dni: str
    monto: Decimal
    linea: int
    linea_nombre: str
    estado: str
    cubica: str
    lote: int
    numero_resolucion: int
    en_resolucion: bool

    model_config = {"from_attributes": True}


class AnexoAsignarIn(BaseModel):
    tipo: int = 6
    resolucion_id: int
    solicitud_ids: list[int] = Field(default_factory=list)


class AnexoQuitarIn(BaseModel):
    solicitud_ids: list[int] = Field(default_factory=list)


# --------------------------------------------------------------------------- expedientes
class ExpedienteIn(BaseModel):
    numero: str
    caratula: str
    iniciador: str | None = ""
    fecha_inicio: date | None = None
    oficina: str | None = ""


class PaseIn(BaseModel):
    oficina_destino: str
    motivo: str | None = ""
    fecha: date | None = None


class PaseOut(BaseModel):
    id: int
    fecha: date
    oficina_origen: str
    oficina_destino: str
    motivo: str
    usuario: str

    model_config = {"from_attributes": True}


class ExpedienteOut(BaseModel):
    id: int
    numero: str
    caratula: str
    iniciador: str
    fecha_inicio: date
    estado: str
    oficina_actual: str

    model_config = {"from_attributes": True}


class ExpedienteDetalle(ExpedienteOut):
    pases: list[PaseOut] = []


# --------------------------------------------------------------------------- importación
class ImportacionOut(BaseModel):
    id: int
    archivo: str
    tamano: int
    estado: str
    modelos: int
    resoluciones: int
    beneficiarios: int
    omitidas: int
    mensaje: str
    creadoEn: datetime | None = None
    terminadoEn: datetime | None = None

    model_config = {"from_attributes": True}


class ListaImportaciones(BaseModel):
    """El listado va envuelto en `items`, igual que el importador del padrón de clientes."""

    items: list[ImportacionOut] = []
