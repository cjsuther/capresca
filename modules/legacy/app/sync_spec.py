"""
Especificación declarativa de sincronización legacy -> mirror.

Para cada tabla legacy define:
  - model:        modelo SQLAlchemy del mirror destino
  - natural_key:  atributos del mirror que forman la clave natural (para upsert)
  - fields:       lista de (mirror_attr, DBF_FIELD, coerción)

IMPORTANTE: los nombres de campo DBF (en MAYÚSCULAS) son PROVISIONALES, derivados
de la documentación, y respetan el límite de FoxPro de 10 caracteres por nombre
de campo. La lectura es case-insensitive y el mapeo está centralizado acá: cuando
se disponga de las DBF reales, ajustar solo este archivo.
"""
from dataclasses import dataclass, field
from typing import Callable

from app.services import coercion as C
from app.models.mirror_juegos import MirrorMaeagencias, MirrorMaejuegos
from app.models.mirror_caja import (
    MirrorCajaliq,
    MirrorCajapagos,
    MirrorCajaforpag,
    MirrorCajacreseg,
)
from app.models.mirror_creditos import (
    MirrorMaeclientes,
    MirrorSolicitud,
    MirrorMaecuotas,
    MirrorLineacred,
)
from app.models.mirror_general import MirrorMaestrodio, MirrorOrganismos


@dataclass
class TableSpec:
    table: str                       # nombre de la tabla legacy (clave del catálogo)
    model: type                      # modelo mirror
    natural_key: list[str]           # atributos del mirror que forman la clave natural
    fields: list[tuple]              # (mirror_attr, DBF_FIELD, coerción)
    watermark_field: str = ""        # atributo mirror para marca de agua incremental (opcional)


SPECS: dict[str, TableSpec] = {
    # ── juegos ──────────────────────────────────────────────────────────
    "maeagencias": TableSpec(
        "maeagencias", MirrorMaeagencias, ["cod_agencia"],
        [
            ("cod_agencia", "COD_AGEN", C.to_str),
            ("titular", "TITULAR", C.to_str),
        ],
    ),
    "maejuegos": TableSpec(
        "maejuegos", MirrorMaejuegos, ["cod_juego"],
        [
            ("cod_juego", "COD_JUEGO", C.to_int),
            ("descripcion", "DESCRIP", C.to_str),
            ("modalidad", "MODALIDAD", C.to_int),
        ],
    ),

    # ── caja ────────────────────────────────────────────────────────────
    "cajaliq": TableSpec(
        "cajaliq", MirrorCajaliq, ["cod_agencia", "cod_juego", "no_sorteo"],
        [
            ("cod_agencia", "COD_AGEN", C.to_str),
            ("cod_juego", "COD_JUEGO", C.to_int),
            ("no_sorteo", "NO_SORTEO", C.to_int),
            ("importe", "IMPORTE", C.to_decimal),
            ("intereses", "INTERESES", C.to_decimal),
            ("pagado", "PAGADO", C.to_bool),
            ("fecha_pago", "FECHA_PAGO", C.to_date),
            ("no_recibo", "NO_RECIBO", C.to_int),
        ],
    ),
    "cajapagos": TableSpec(
        "cajapagos", MirrorCajapagos, ["no_recibo"],
        [
            ("no_recibo", "NO_RECIBO", C.to_int),
            ("cod_agencia", "COD_AGEN", C.to_str),
            ("fecha_pago", "FECHA_PAGO", C.to_date),
            ("origen", "ORIGEN", C.to_str),
            ("total", "TOTAL", C.to_decimal),
            ("bonos", "BONOS", C.to_decimal),
            ("pesos", "PESOS", C.to_decimal),
            ("cajero", "CAJERO", C.to_str),
        ],
        watermark_field="no_recibo",
    ),
    "cajaforpag": TableSpec(
        "cajaforpag", MirrorCajaforpag, ["no_recibo", "sno_recibo"],
        [
            ("no_recibo", "NO_RECIBO", C.to_int),
            ("sno_recibo", "SNO_RECIBO", C.to_int),
            ("moneda", "MONEDA", C.to_str),
            ("origen", "ORIGEN", C.to_str),
            ("fecha_pago", "FECHA_PAGO", C.to_date),
            ("anulado", "ANULADO", C.to_bool),
        ],
    ),
    "cajacreseg": TableSpec(
        "cajacreseg", MirrorCajacreseg, ["nrecibo", "recofi"],
        [
            ("nrecibo", "NRECIBO", C.to_int),
            ("recofi", "RECOFI", C.to_int),
            ("origen", "ORIGEN", C.to_str),
            ("fecha_pago", "FECHA_PAGO", C.to_date),
            ("via_pago", "VIA_PAGO", C.to_str),
            ("usuario_pago", "USU_PAGO", C.to_str),
        ],
    ),

    # ── creditos ────────────────────────────────────────────────────────
    "maeclientes": TableSpec(
        "maeclientes", MirrorMaeclientes, ["cuil"],
        [
            ("cuil", "CUIL", C.to_str),
            ("nombre", "NOMBRE", C.to_str),
            ("domicilio", "DOMICILIO", C.to_str),
        ],
    ),
    "solicitud": TableSpec(
        "solicitud", MirrorSolicitud, ["no_credito"],
        [
            ("no_credito", "NO_CREDITO", C.to_int),
            ("cuil", "CUIL", C.to_str),
            ("estado", "ESTADO", C.to_str),
            ("monto", "MONTO", C.to_decimal),
            ("tasa", "TASA", C.to_decimal),
            ("ga_cuil", "GA_CUIL", C.to_str),
            ("g2_cuil", "G2_CUIL", C.to_str),
            ("g3_cuil", "G3_CUIL", C.to_str),
            ("g4_cuil", "G4_CUIL", C.to_str),
        ],
    ),
    "maecuotas": TableSpec(
        "maecuotas", MirrorMaecuotas, ["no_credito", "no_cuota"],
        [
            ("no_credito", "NO_CREDITO", C.to_int),
            ("no_cuota", "NO_CUOTA", C.to_int),
            ("estado", "ESTADO", C.to_str),
            ("fecha_vto", "FECHA_VTO", C.to_date),
            ("total_vdo", "TOTAL_VDO", C.to_decimal),
        ],
    ),
    "lineacred": TableSpec(
        "lineacred", MirrorLineacred, ["cod_linea"],
        [
            ("cod_linea", "COD_LINEA", C.to_int),
            ("descripcion", "DESCRIP", C.to_str),
            ("nmoradia", "NMORADIA", C.to_decimal),
        ],
    ),

    # ── general ─────────────────────────────────────────────────────────
    "maestrodio": TableSpec(
        "maestrodio", MirrorMaestrodio, ["legajo"],
        [
            ("legajo", "LEGAJO", C.to_str),
            ("cuil", "CUIL", C.to_str),
            ("nombre", "NOMBRE", C.to_str),
            ("haberes", "HABERES", C.to_decimal),
        ],
    ),
    "organismos": TableSpec(
        "organismos", MirrorOrganismos, ["cod_organismo"],
        [
            ("cod_organismo", "COD_ORG", C.to_str),
            ("descripcion", "DESCRIP", C.to_str),
            ("capresca", "CAPRESCA", C.to_str),
        ],
    ),
}


# Tablas sincronizables (las consolidadas de contabilidad NO se espejan por defecto)
SYNCABLE_TABLES = tuple(SPECS.keys())
