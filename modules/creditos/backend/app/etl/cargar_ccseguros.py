"""ETL de la cuenta corriente de seguros por agente (Seguros/ccseguros.dbf, ~180 mil).
Cargos de seguro por agente/período. Enriquece la Visión 360 del cliente.

Uso: python -m app.etl.cargar_ccseguros "/ruta/a/bases"
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


def _fecha(v):
    if isinstance(v, datetime.datetime):
        v = v.date()
    return v if isinstance(v, datetime.date) and 1970 <= v.year <= 2100 else None


def cargar(bases: str):
    db = SessionLocal()
    p = os.path.join(bases, "Seguros", "ccseguros.dbf")
    if not os.path.exists(p) or db.query(models.CtaCteSeguro).first():
        print("  cta.cte. de seguros: omito (no existe o ya cargada)")
        db.close()
        return
    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            if x.get("_deleted"):
                continue
            x = {k.lower(): v for k, v in x.items()}
            cuil = S(x.get("cuil"))[:11]
            nag = I(x.get("no_agente"))
            if not cuil and not nag:
                continue
            batch.append({
                "cuil": cuil, "no_agente": nag, "sexo": S(x.get("sexo"))[:1],
                "periodo": S(x.get("periodo"))[:6], "seguro": I(x.get("seguro")),
                "importe": D(x.get("importe")), "fecha_alta": _fecha(x.get("fecha_alta")),
            })
            if len(batch) >= 10000:
                db.bulk_insert_mappings(models.CtaCteSeguro, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.CtaCteSeguro, batch); db.commit(); total += len(batch)
    print(f"  cta.cte. de seguros: {total}")
    db.close()


if __name__ == "__main__":
    cargar(sys.argv[1])
