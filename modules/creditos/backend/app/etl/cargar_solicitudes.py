"""ETL de solicitudes de crédito reales (agjscreditos!solicitud) para el Anexo
de Resolución. Reconstruido del fuente 120100000anexo_res_dis (H-026).

Uso: python -m app.etl.cargar_solicitudes "/ruta/a/bases"
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
    return v if isinstance(v, datetime.date) and v.year >= 1990 else None


def cargar(bases: str):
    db = SessionLocal()
    p = os.path.join(bases, "Creditos", "solicitud.dbf")
    if not os.path.exists(p) or db.query(models.SolicitudCredito).first():
        print("  solicitudes: omito (no existe o ya cargadas)")
        db.close()
        return
    batch, total = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            nid = I(x.get("no_solicit"))
            if not nid:
                continue
            batch.append({
                "id": nid, "fecha_soli": _fecha(x.get("fecha_soli")),
                "cuil": S(x.get("so_cuil"))[:11], "apellido_nombre": S(x.get("so_apenom"))[:80],
                "dni": S(x.get("so_dni"))[:9], "montosol": D(x.get("montosol")),
                "no_credpp": I(x.get("no_credpp")), "importepp": D(x.get("importepp")),
                "linea": I(x.get("linea")), "estado": S(x.get("estado"))[:2],
                "cubica": S(x.get("cubica"))[:2], "no_resol": I(x.get("no_resol")),
                "fecha_resol": _fecha(x.get("fecha_resol")),
                "en_reso": bool(x.get("en_reso")), "lote": I(x.get("lote")),
            })
            if len(batch) >= 5000:
                db.bulk_insert_mappings(models.SolicitudCredito, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.SolicitudCredito, batch); db.commit(); total += len(batch)
    print(f"  solicitudes de crédito: {total}")
    db.close()


if __name__ == "__main__":
    cargar(sys.argv[1])
