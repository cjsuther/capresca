"""ETL: cuenta corriente (ctacte) de los créditos cargados.

Uso:
    DATABASE_URL=sqlite+pysqlite:///./ccypp_real.db \
    python3 -m app.etl.cargar_ctacte "/ruta/a/bases"
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


def cargar(bases: str):
    db = SessionLocal()
    if db.query(models.MovimientoCta).first():
        print("  ya hay movimientos; omito")
        return
    cred_ids = {c for (c,) in db.query(models.Credito.id).all()}
    p = os.path.join(bases, "Creditos", "ctacte.dbf")
    if not os.path.exists(p):
        print("  no se encontró ctacte.dbf")
        return

    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            nc = I(x.get("nno_credit"))
            if nc not in cred_ids:
                continue
            f = x.get("tfecha")
            batch.append({
                "credito_id": nc, "cuota": I(x.get("nno_cuota")),
                "fecha": f.date() if hasattr(f, "date") else (f if isinstance(f, datetime.date) else None),
                "tipo": S(x.get("ctipo"))[:4],
                "debitos": D(x.get("ndebitos")), "creditos": D(x.get("ncreditos")),
                "capital": D(x.get("ncapital")), "interes": D(x.get("ninteres")),
                "iva": D(x.get("niva")), "punitorio": D(x.get("nint_puni")),
                "no_recibo": I(x.get("nno_recibo")),
            })
            if len(batch) >= 5000:
                db.bulk_insert_mappings(models.MovimientoCta, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.MovimientoCta, batch); db.commit(); total += len(batch)
    print(f"  movimientos de cuenta corriente: {total}")
    print("ETL ctacte OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
