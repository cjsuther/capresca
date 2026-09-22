"""ETL Contabilidad: carga el libro mayor real (asientos.dbf, ~2M movimientos).

Uso:
    docker compose exec -d backend python -m app.etl.cargar_contable /bases
"""
from __future__ import annotations

import os
import sys
import datetime
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


def _fecha(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    return v if isinstance(v, datetime.date) else None


def cargar(bases: str):
    db = SessionLocal()
    if db.query(models.MovimientoContable).first():
        print("  ya hay movimientos contables; omito")
        return
    p = os.path.join(bases, "Contabilidad", "asientos.dbf")
    if not os.path.exists(p):
        print("  no se encontró asientos.dbf")
        return

    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            batch.append({
                "cuenta": S(x.get("cuenta"))[:20], "ctaplan": S(x.get("ctaplan"))[:20],
                "fecha": _fecha(x.get("fecha")), "periodo": S(x.get("cperio"))[:6],
                "fecha_pago": _fecha(x.get("fecpago")), "norden": I(x.get("norden")),
                "debito": D(x.get("ndebito")), "credito": D(x.get("ncredito")),
                "referencia": S(x.get("creferenci"))[:24],
            })
            if len(batch) >= 10000:
                db.bulk_insert_mappings(models.MovimientoContable, batch)
                db.commit(); total += len(batch); batch = []
                if total % 100000 == 0:
                    print(f"  ...{total}")
    if batch:
        db.bulk_insert_mappings(models.MovimientoContable, batch); db.commit(); total += len(batch)
    print(f"  movimientos contables: {total}")
    print("ETL contable OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
