"""ETL del ledger real de egresos (Egresos/egresos.dbf, ~340 mil). Alimenta la
'Busca transacciones de egresos' (menú 81505).

Uso: python -m app.etl.cargar_egresos_ledger "/ruta/a/bases"
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


def S(v):
    return str(v).strip() if v is not None else ""


def _fecha(v):
    if isinstance(v, datetime.datetime):
        v = v.date()
    return v if isinstance(v, datetime.date) and 1990 <= v.year <= 2100 else None


def cargar(bases: str):
    db = SessionLocal()
    p = os.path.join(bases, "Egresos", "egresos.dbf")
    if not os.path.exists(p) or db.query(models.Egreso).first():
        print("  egresos (ledger): omito (no existe o ya cargados)")
        db.close()
        return
    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            if x.get("_deleted"):
                continue
            x = {k.lower(): v for k, v in x.items()}
            batch.append({
                "tipo_egreso": I(x.get("tipo_egres")),
                "sub_tipo": I(x.get("sub_tipo")),
                "no_liquida": I(x.get("no_liquida")),
                "fecha_liqu": _fecha(x.get("fecha_liqu")),
                "tipo_res": I(x.get("tipo_res")),
                "nro_res": I(x.get("nro_res")),
                "fec_res": _fecha(x.get("fec_res")),
                "no_credito": I(x.get("no_credito")),
                "no_solicit": I(x.get("no_solicit")),
                "apenom": S(x.get("apenom"))[:40],
                "cuil": S(x.get("cuil"))[:11],
                "no_op": I(x.get("no_op")),
                "fecha_op": _fecha(x.get("fecha_op")),
                "no_cheque": I(x.get("no_cheque")),
                "banco": I(x.get("banco")),
                "no_recibo": I(x.get("no_recibo")),
                "no_cuota": I(x.get("no_cuota")),
                "importe": D(x.get("importe")),
                "retenciones": D(x.get("retencione")),
                "total": D(x.get("total")),
                "fecha_pago": _fecha(x.get("fechapago")),
                "pagado": B(x.get("pagado")),
                "anulado": B(x.get("lanulada")),
            })
            if len(batch) >= 10000:
                db.bulk_insert_mappings(models.Egreso, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.Egreso, batch); db.commit(); total += len(batch)
    print(f"  egresos (ledger): {total}")
    db.close()


if __name__ == "__main__":
    cargar(sys.argv[1])
