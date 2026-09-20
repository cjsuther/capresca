"""ETL de liquidaciones de agencia históricas (Juegos/jghisliq.dbf, ~273 mil).
Archivo generado por el proceso 42515 (pasa liquidaciones a histórico). Alimenta
el informe de Fondo de Garantía (43025), que une jghisliq + liquidaciones.

Uso: python -m app.etl.cargar_hisliq "/ruta/a/bases"
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


def B(v):
    return v is True or str(v).strip().lower() in ("true", "t", ".t.", "1", "s")


def _fecha(v):
    if isinstance(v, datetime.datetime):
        v = v.date()
    return v if isinstance(v, datetime.date) and v.year >= 1970 else None


def cargar(bases: str):
    db = SessionLocal()
    p = os.path.join(bases, "Juegos", "jghisliq.DBF")
    if not os.path.exists(p):
        p = os.path.join(bases, "Juegos", "jghisliq.dbf")
    if not os.path.exists(p) or db.query(models.LiquidacionHistorica).first():
        print("  liquidaciones históricas: omito (no existe o ya cargadas)")
        db.close()
        return
    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            if x.get("_deleted"):
                continue
            x = {k.lower(): v for k, v in x.items()}
            batch.append({
                "cod_agencia": I(x.get("cod_agenci")),
                "no_agencia": I(x.get("no_agencia")),
                "subagencia": I(x.get("no_subagen")),
                "cod_juego": I(x.get("cod_juego")),
                "modalidad": I(x.get("modalidad")),
                "no_sorteo": I(x.get("no_sorteo")),
                "fecha": _fecha(x.get("fecha")),
                "interior": B(x.get("interior")),
                "moneda": (str(x.get("moneda") or "").strip())[:4],
                "recaudacion": D(x.get("recaudacio")),
                "premios": D(x.get("premios")),
                "com_premios": D(x.get("com_premio")),
                "multas": D(x.get("multas")),
                "com_agencia": D(x.get("com_agenci")),
                "com_subagencia": D(x.get("com_subage")),
                "fdo_gtia": D(x.get("fdo_gtia")),
                "ing_brutos": D(x.get("ing_brutos")),
                "total": D(x.get("total")),
            })
            if len(batch) >= 10000:
                db.bulk_insert_mappings(models.LiquidacionHistorica, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.LiquidacionHistorica, batch); db.commit(); total += len(batch)
    print(f"  liquidaciones de agencia históricas: {total}")
    db.close()


if __name__ == "__main__":
    cargar(sys.argv[1])
