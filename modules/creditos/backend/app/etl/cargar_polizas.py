"""ETL de pólizas de seguro de vida colectivo por agente (Seguros/seguros.dbf,
~207 mil registros). Alimenta la pantalla 'Pólizas vigentes' del módulo Seguros.

Uso: python -m app.etl.cargar_polizas "/ruta/a/bases"
"""
from __future__ import annotations

import datetime
import os
import sys

from app.core.database import SessionLocal
from app.etl.dbf import DbfReader
from app import models


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
    return v if isinstance(v, datetime.date) and v.year >= 1970 else None


def cargar(bases: str):
    db = SessionLocal()
    p = os.path.join(bases, "Seguros", "seguros.DBF")
    if not os.path.exists(p):
        p = os.path.join(bases, "Seguros", "seguros.dbf")
    if not os.path.exists(p) or db.query(models.PolizaAgente).first():
        print("  pólizas de agente: omito (no existe o ya cargadas)")
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
                "codigo": I(x.get("codigo")),
                "no_poliza": I(x.get("no_poliza")),
                "cuil": cuil,
                "no_agente": nag,
                "sexo": S(x.get("sexo"))[:1],
                "estado": (S(x.get("estado")) or "A")[:2],
                "baja": B(x.get("baja")),
                "cantidad": I(x.get("cantidad"), 1),
                "fecha": _fecha(x.get("fecha")),
                "fecha_alta": _fecha(x.get("fecha_alta")),
            })
            if len(batch) >= 5000:
                db.bulk_insert_mappings(models.PolizaAgente, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.PolizaAgente, batch); db.commit(); total += len(batch)
    print(f"  pólizas de seguro por agente: {total}")
    db.close()


if __name__ == "__main__":
    cargar(sys.argv[1])
