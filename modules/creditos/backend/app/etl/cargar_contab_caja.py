"""ETL de tablas de Contabilidad y Caja no cubiertas antes:
  - crctacte.dbf  → CtaCteContableCredito  (cta. cte. contable de créditos, ~1M)
  - contgral.dbf  → ContabilidadGeneral    (contab. general de caja/juegos, ~106k)
  - cj_crsghis.dbf → CajaCreSegHistorico    (crédito/seguro cobrado histórico, ~143k)

Cada uno expone su propio `cargar(bases)` para el registro de migradores.

Uso: python -m app.etl.cargar_contab_caja <crctacte|contgral|cj_crsghis> "/bases"
"""
from __future__ import annotations

import datetime
import os
import sys
from decimal import Decimal, InvalidOperation

from app.core.database import SessionLocal
from app.etl.dbf import DbfReader
from app import models


def D(v):
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal("0")
    except (InvalidOperation, ValueError):
        return Decimal("0")


def I(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def S(v):
    return str(v).strip() if v is not None else ""


def B(v):
    return v is True or S(v).lower() in ("true", "t", ".t.", "1", "s")


def _fecha(v):
    if isinstance(v, datetime.datetime):
        v = v.date()
    return v if isinstance(v, datetime.date) and 1970 <= v.year <= 2100 else None


def _cargar(bases: str, carpeta: str, archivo: str, modelo, fila_fn, nombre: str):
    db = SessionLocal()
    p = os.path.join(bases, carpeta, archivo)
    if not os.path.exists(p) or db.query(modelo).first():
        print(f"  {nombre}: omito (no existe o ya cargada)")
        db.close()
        return
    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            if x.get("_deleted"):
                continue
            x = {k.lower(): v for k, v in x.items()}
            fila = fila_fn(x)
            if fila is None:
                continue
            batch.append(fila)
            if len(batch) >= 10000:
                db.bulk_insert_mappings(modelo, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(modelo, batch); db.commit(); total += len(batch)
    print(f"  {nombre}: {total}")
    db.close()


# ---- crctacte → CtaCteContableCredito ----
def _fila_crctacte(x):
    ncred = I(x.get("ncredito"))
    if not ncred:
        return None
    return {
        "cuenta": S(x.get("cuenta"))[:12], "no_credito": ncred, "no_cuota": I(x.get("ncuota")),
        "corga": S(x.get("corga"))[:6], "fecha_vto": _fecha(x.get("fecvto")),
        "fecha_pago": _fecha(x.get("fechapago")), "via_pago": S(x.get("via_pago"))[:8],
        "cod_mov": I(x.get("ncodmov")), "signo": I(x.get("nsigno")),
        "debitos": D(x.get("ndebitos")), "creditos": D(x.get("ncreditos")), "saldo": D(x.get("nsaldo")),
        "capital": D(x.get("ncapital")), "int_normal": D(x.get("nintnor")), "iva_normal": D(x.get("nivanor")),
        "gastos": D(x.get("ngsas")), "sellado": D(x.get("nsellado")),
        "int_punit": D(x.get("nintpun")), "iva_punit": D(x.get("nivapun")),
        "int_resarc": D(x.get("nintres")), "iva_resarc": D(x.get("nivares")),
        "anulada": B(x.get("lanulada")),
    }


def cargar_crctacte(bases: str):
    _cargar(bases, "Contabilidad", "crctacte.dbf", models.CtaCteContableCredito,
            _fila_crctacte, "cta.cte. contable de créditos")


# ---- contgral → ContabilidadGeneral ----
def _fila_contgral(x):
    return {
        "fecha": _fecha(x.get("fecha")), "periodo": S(x.get("naamm"))[:6], "asiento": I(x.get("nasiento")),
        "recibo": I(x.get("nrecibo")), "tipo": S(x.get("ctipo"))[:1], "agencia": I(x.get("nagencia")),
        "subagencia": I(x.get("nsubage")), "apellido_nombre": S(x.get("capenom"))[:60],
        "destino": S(x.get("cdestino"))[:20], "origen": S(x.get("corigen"))[:8],
        "sorteo": I(x.get("nsorteo")), "cuota": I(x.get("ncuota")), "moneda": S(x.get("cmoneda"))[:4],
        "total_pesos": D(x.get("ntotpes")), "total_bonos": D(x.get("ntotbon")),
        "total_bono2": D(x.get("ntotbo2")), "total_lecop": D(x.get("ntotlec")),
    }


def cargar_contgral(bases: str):
    _cargar(bases, "Contabilidad", "contgral.dbf", models.ContabilidadGeneral,
            _fila_contgral, "contabilidad general")


# ---- cj_crsghis → CajaCreSegHistorico ----
def _fila_crsghis(x):
    return {
        "origen": S(x.get("origen"))[:8], "no_credito": I(x.get("no_credito")),
        "cuil": S(x.get("cuil"))[:11], "apellido_nombre": S(x.get("apenom"))[:60],
        "cuota": I(x.get("cualcuo") or x.get("cuota")), "interes": D(x.get("interes")),
        "seguro": D(x.get("nseg") or x.get("seguro")), "gastos": D(x.get("gastos")),
        "total": D(x.get("total")), "total_gral": D(x.get("total_gral")),
        "moneda": S(x.get("moneda"))[:4], "fecha_pago": _fecha(x.get("fecha_pago")),
        "no_recibo": I(x.get("no_recibo")),
    }


def cargar_crsghis(bases: str):
    _cargar(bases, "Caja", "cj_crsghis.dbf", models.CajaCreSegHistorico,
            _fila_crsghis, "crédito/seguro cobrado histórico")


# ---- cj_liqhis → LiquidacionAgenciaHistorica ----
def _fila_liqhis(x):
    return {
        "cod_agencia": I(x.get("cod_agenci")), "no_agencia": I(x.get("no_agencia")),
        "subagencia": I(x.get("no_subagen")), "cod_juego": I(x.get("cod_juego")),
        "juego": S(x.get("cjuego"))[:30], "no_sorteo": I(x.get("no_sorteo")),
        "fecha_sorteo": _fecha(x.get("fecha_sort")), "interior": B(x.get("interior")),
        "moneda": S(x.get("moneda"))[:4], "recaudacion": D(x.get("recaudacio")),
        "premios": D(x.get("premios")), "com_premios": D(x.get("com_premio")),
        "comision_agencia": D(x.get("com_agenci")), "comision_subagencia": D(x.get("com_subage")),
        "multas": D(x.get("multas")), "ing_brutos": D(x.get("ing_brutos")),
        "fdo_gtia": D(x.get("fdo_gtia")), "total": D(x.get("total")),
        "intereses": D(x.get("intereses")), "iva": D(x.get("iva")),
        "total_gral": D(x.get("total_gral")), "fecha_vto": _fecha(x.get("fecha_vto")),
        "pagado": B(x.get("pagado")), "fecha_pago": _fecha(x.get("fecha_pago")),
        "cajero": S(x.get("cajero"))[:20], "no_recibo": I(x.get("no_recibo")),
        "anulado": B(x.get("lanula")),
    }


def cargar_liqhis(bases: str):
    _cargar(bases, "Caja", "cj_liqhis.dbf", models.LiquidacionAgenciaHistorica,
            _fila_liqhis, "liquidaciones de agencia (histórico)")


# ---- cj_paghis → CajaPagoAgenciaHistorico ----
def _fila_paghis(x):
    return {
        "cod_agencia": I(x.get("cod_agenci")), "fecha_pago": _fecha(x.get("fecha_pago")),
        "origen": S(x.get("origen"))[:8], "no_recibo": I(x.get("no_recibo")),
        "bonos": D(x.get("bonos")), "pesos": D(x.get("pesos")), "total": D(x.get("total")),
        "cobrado_bonos": D(x.get("cobrado_bo")), "cobrado_pesos": D(x.get("cobrado_pe")),
        "cobrado_total": D(x.get("cobrado_to")), "vuelto_bonos": D(x.get("vuelto_bon")),
        "vuelto_pesos": D(x.get("vuelto_pes")), "premios_bonos": D(x.get("premios_bo")),
        "premios_pesos": D(x.get("premios_pe")), "cajero": S(x.get("cajero"))[:20],
        "anulado": B(x.get("anulado")),
    }


def cargar_paghis(bases: str):
    _cargar(bases, "Caja", "cj_paghis.dbf", models.CajaPagoAgenciaHistorico,
            _fila_paghis, "pagos de agencia (histórico)")


if __name__ == "__main__":
    cual = sys.argv[1]; bases = sys.argv[2] if len(sys.argv) > 2 else "/bases"
    {"crctacte": cargar_crctacte, "contgral": cargar_contgral, "cj_crsghis": cargar_crsghis,
     "cj_liqhis": cargar_liqhis, "cj_paghis": cargar_paghis}[cual](bases)
