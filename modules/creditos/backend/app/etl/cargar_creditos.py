"""ETL etapa 2: créditos activos (crcliact) + sus cuotas (maecuotas) reales.

Uso:
    DATABASE_URL=sqlite+pysqlite:///./ccypp_real.db \
    python3 -m app.etl.cargar_creditos "/ruta/a/bases"
"""
from __future__ import annotations

import datetime
import os
import sys
from decimal import Decimal, InvalidOperation

from sqlalchemy import select, func

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
    creds_dir = os.path.join(bases, "Creditos")

    if db.query(models.Credito).first():
        print("  ya hay créditos cargados; omito")
        return

    # lookups
    cli_by_id = {c.id_cliente: c.id for c in db.query(
        models.Cliente.id_cliente, models.Cliente.id).all()}
    cli_by_cuil = {c.cuil: c.id for c in db.query(
        models.Cliente.cuil, models.Cliente.id).all()}
    linea_ids = {l for (l,) in db.query(models.LineaCredito.id).all()}

    # ---- crcliact -> creditos ----
    creditos = []
    cred_ids = set()
    p = os.path.join(creds_dir, "crcliact.dbf")
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            nocred = I(x.get("nocred"))
            if not nocred or nocred in cred_ids:
                continue
            cid = cli_by_id.get(S(x.get("cidcli"))[:15]) or cli_by_cuil.get(S(x.get("cuil"))[:11])
            if not cid:
                continue
            nlinea = I(x.get("nlinea"))
            saldo = D(x.get("nsdonor"))
            estado = "A" if not x.get("cestado") or S(x.get("cestado")).upper().startswith("A") else \
                ("C" if S(x.get("cestado")).upper().startswith("C") else "A")
            creditos.append({
                "id": nocred, "solicitud_id": None,
                "linea_id": nlinea if nlinea in linea_ids else None,
                "cliente_id": cid, "capital": saldo, "saldo_capital": saldo,
                "fecha_otorgamiento": (x.get("fecha").date() if hasattr(x.get("fecha"), "date") else x.get("fecha")),
                "estado": estado,
            })
            cred_ids.add(nocred)
    db.bulk_insert_mappings(models.Credito, creditos)
    db.commit()
    print(f"  créditos: {len(creditos)}")

    # ---- maecuotas -> cuotas (sólo de los créditos cargados) ----
    ESTADOS = {"P": "P", "A": "A", "M": "M", "C": "P"}
    batch, total = [], 0
    cap_por_credito: dict[int, Decimal] = {}
    p = os.path.join(creds_dir, "maecuotas.dbf")
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            nc = I(x.get("no_credito"))
            if nc not in cred_ids:
                continue
            amort = D(x.get("capital"))
            cap_por_credito[nc] = cap_por_credito.get(nc, Decimal("0")) + amort
            tp = D(x.get("total_paga"))
            est = ESTADOS.get(S(x.get("estado")).upper()[:1], "A")
            fp = x.get("fecha_pago")
            if isinstance(fp, datetime.datetime):
                fp = fp.date()
            elif not isinstance(fp, datetime.date):
                fp = None
            batch.append({
                "credito_id": nc, "numero": I(x.get("no_cuota")),
                "fecha_vencimiento": x.get("fecha_vto"),
                "saldo_capital": D(x.get("sdo_cap")), "amortizacion": amort,
                "interes": D(x.get("interes")), "iva_interes": D(x.get("iva_intere")),
                "seguro": D(x.get("ngseg")), "iva_seguro": D(x.get("nivaseg")),
                "gastos_adm": D(x.get("ngadm")), "iva_gastos_adm": D(x.get("nivaadm")),
                "total": D(x.get("total")), "total_pagado": tp, "estado": est,
                "fecha_pago": fp, "nro_recibo": I(x.get("nrecibo")),
                "via_pago": S(x.get("via_pago"))[:10], "usuario_pago": S(x.get("usuario_pa"))[:30],
            })
            if len(batch) >= 5000:
                db.bulk_insert_mappings(models.Cuota, batch)
                db.commit(); total += len(batch); batch = []
    if batch:
        db.bulk_insert_mappings(models.Cuota, batch); db.commit(); total += len(batch)
    print(f"  cuotas: {total}")

    # ---- turnos otorgados (turnos) ----
    p = os.path.join(creds_dir, "turnos.dbf")
    if os.path.exists(p) and not db.query(models.TurnoCredito).first():
        batch, tt = [], 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                f = x.get("fecha")
                batch.append({
                    "tipo": S(x.get("ctipo"))[:10], "numero": I(x.get("nturno")),
                    "periodo": S(x.get("periodo"))[:6],
                    "fecha": f if isinstance(f, datetime.date) else None,
                    "cuil": S(x.get("cuilsol"))[:11],
                    "apellido_nombre": S(x.get("capenoms"))[:80],
                    "linea": I(x.get("nlinea")), "sueldo": D(x.get("nsueldos")),
                    "usado": bool(x.get("lusado")), "autorizado": bool(x.get("lautoriza")),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.TurnoCredito, batch); db.commit(); tt += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.TurnoCredito, batch); db.commit(); tt += len(batch)
        print(f"  turnos de crédito: {tt}")

    # capital real = suma de amortizaciones
    for nc, cap in cap_por_credito.items():
        if cap > 0:
            db.query(models.Credito).filter_by(id=nc).update({"capital": cap})
    db.commit()
    print("ETL créditos OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
