"""ETL de cheques emitidos por Tesorería (Egresos/cheques.dbf, ~73 mil). Alimenta
el 'Listado de cheques emitidos en una fecha' (menú 83040).

Uso: python -m app.etl.cargar_cheques "/ruta/a/bases"
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
    p = os.path.join(bases, "Egresos", "cheques.dbf")
    if not os.path.exists(p) or db.query(models.ChequeEmitido).first():
        print("  cheques emitidos: omito (no existe o ya cargados)")
        db.close()
        return
    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            if x.get("_deleted"):
                continue
            x = {k.lower(): v for k, v in x.items()}
            batch.append({
                "banco": I(x.get("nbanco")),
                "ncuenta": I(x.get("ncuenta")),
                "cuenta": (str(x.get("cuenta") or "").strip())[:20],
                "ncheque": I(x.get("ncheque")),
                "fecha": _fecha(x.get("fecha")),
                "importe": D(x.get("nimporte")),
                "nop": I(x.get("nop")),
                "fop": _fecha(x.get("fop")),
                "nres": I(x.get("nres")),
                "fres": _fecha(x.get("fres")),
                "nliqui": I(x.get("nliqui")),
                "anulado": B(x.get("lanula")),
            })
            if len(batch) >= 10000:
                db.bulk_insert_mappings(models.ChequeEmitido, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.ChequeEmitido, batch); db.commit(); total += len(batch)
    print(f"  cheques emitidos: {total}")
    db.close()


if __name__ == "__main__":
    cargar(sys.argv[1])
