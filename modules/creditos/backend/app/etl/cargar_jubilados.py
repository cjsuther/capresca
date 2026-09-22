"""ETL: créditos de jubilados / Ley 5094 (sol_jubi + jub_ctas).

Uso:
    DATABASE_URL=... python3 -m app.etl.cargar_jubilados "/bases"
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


def F(v):
    return v if isinstance(v, datetime.date) else None


def cargar(bases: str):
    db = SessionLocal()
    cd = os.path.join(bases, "Creditos")
    if db.query(models.CreditoJubilado).first():
        print("  ya hay créditos de jubilado; omito")
        return

    ids = set()
    p = os.path.join(cd, "sol_jubi.dbf")
    if os.path.exists(p):
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                nid = I(x.get("no_solicit"))
                if not nid or nid in ids:
                    continue
                ids.add(nid)
                rows.append({
                    "id": nid, "beneficiario_nro": I(x.get("no_benefic")),
                    "cuil": S(x.get("cuil"))[:11], "apellido_nombre": S(x.get("ape_nom"))[:80],
                    "domicilio": S(x.get("domicilio"))[:120], "localidad": S(x.get("localidad"))[:40],
                    "departamento": S(x.get("depto"))[:40], "haberes": D(x.get("haberes")),
                    "monto": D(x.get("monto")), "cantidad_cuotas": I(x.get("cuotas")),
                    "liquidada": bool(x.get("liquidada")),
                    "numero_resolucion": S(x.get("no_resoluc"))[:20],
                    "prorroga": bool(x.get("prorroga")), "fecha_alta": F(x.get("fecha_alta")),
                })
        db.bulk_insert_mappings(models.CreditoJubilado, rows)
        db.commit()
        print(f"  solicitudes jubilados: {len(rows)}")

    p = os.path.join(cd, "jub_ctas.dbf")
    if os.path.exists(p):
        batch, total = [], 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                sid = I(x.get("no_solicit"))
                if sid not in ids:
                    continue
                batch.append({
                    "credito_jubilado_id": sid, "cuil": S(x.get("cuil"))[:11],
                    "numero": I(x.get("no_cuota")), "valor": D(x.get("valor_cta")),
                    "fecha_vencimiento": F(x.get("fecha_vto")), "pagada": bool(x.get("pagada")),
                    "fecha_pago": F(x.get("fecha_pago")),
                    "numero_resolucion": S(x.get("no_resoluc"))[:20], "no_op": I(x.get("no_op")),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.CuotaJubilado, batch)
                    db.commit(); total += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.CuotaJubilado, batch); db.commit(); total += len(batch)
        print(f"  cuotas jubilados: {total}")
    print("ETL jubilados OK")


if __name__ == "__main__":
    cargar(sys.argv[1] if len(sys.argv) > 1 else "/bases")
