"""ETL Egresos: carga las órdenes de pago reales (agregadas por no_op) desde el
detalle de egresos del backup.

Uso:
    DATABASE_URL=sqlite+pysqlite:///./ccypp_real.db \
    python3 -m app.etl.cargar_egresos "/ruta/a/bases"
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
    p = os.path.join(bases, "Egresos", "egresos.dbf")
    if db.query(models.OrdenPago).first():
        print("  ya hay órdenes de pago; omito")
    elif not os.path.exists(p):
        print("  no se encontró egresos.dbf")
    else:
        _cargar_ordenes(db, p)
    _cargar_maeop(db, bases)
    print("ETL egresos OK")


def _cargar_ordenes(db, p):
    ops: dict[int, dict] = {}
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            nop = I(x.get("no_op"))
            if not nop:
                continue
            imp = D(x.get("importe")) or D(x.get("total"))
            o = ops.get(nop)
            if not o:
                fop = x.get("fecha_op")
                ops[nop] = {
                    "numero": nop,
                    "fecha": fop if isinstance(fop, datetime.date) else datetime.date(2020, 1, 1),
                    "beneficiario": (S(x.get("apenom")) or "S/D")[:80],
                    "cuit_beneficiario": S(x.get("cuil"))[:11],
                    "concepto": f"Egreso crédito N° {I(x.get('no_credito'))}" if I(x.get("no_credito")) else "Egreso",
                    "tipo": "CREDITO" if I(x.get("no_credito")) else "PROVEEDOR",
                    "importe": imp, "iva": Decimal("0"),
                    "estado": "G" if x.get("pagado") else "P",
                    "banco": "", "cheque_numero": S(x.get("no_cheque")),
                    "fecha_pago": None, "credito_id": None,
                }
            else:
                o["importe"] += imp
                if x.get("pagado"):
                    o["estado"] = "G"

    rows = list(ops.values())
    B, total = 5000, 0
    for i in range(0, len(rows), B):
        db.bulk_insert_mappings(models.OrdenPago, rows[i:i + B])
        db.commit(); total += len(rows[i:i + B])
    print(f"  órdenes de pago: {total}")


def _cargar_maeop(db, bases):
    # ---- Maestro de OP = cupos autorizados (maeop / frm805100000altaop) ----
    pm = os.path.join(bases, "Egresos", "maeop.dbf")
    if os.path.exists(pm) and not db.query(models.AutorizacionOP).first():
        def _d(v):
            return v if isinstance(v, datetime.date) and not isinstance(v, datetime.datetime) \
                else (v.date() if isinstance(v, datetime.datetime) else None)
        batch, tot = [], 0
        with DbfReader(pm) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                batch.append({
                    "nop": I(x.get("nop")), "fecha": _d(x.get("fechaop")),
                    "vigencia": _d(x.get("fvigencia")), "importe": D(x.get("nimporte")),
                    "importe_usado": D(x.get("nimpusa")), "saldo": D(x.get("nsaldo")),
                    "sistema": (S(x.get("csistema")) or S(x.get("csis")))[:20],
                    "habilitada": bool(x.get("lhabilitad")),
                    "cancelada": bool(x.get("lcancelada")), "anulada": bool(x.get("lanula")),
                    "nres1": I(x.get("nres1")), "fres1": _d(x.get("fres1")),
                    "nres2": I(x.get("nres2")), "fres2": _d(x.get("fres2")),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.AutorizacionOP, batch)
                    db.commit(); tot += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.AutorizacionOP, batch); db.commit(); tot += len(batch)
        print(f"  autorizaciones de OP (maeop): {tot}")
    print("ETL egresos OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
