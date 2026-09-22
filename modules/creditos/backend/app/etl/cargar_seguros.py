"""ETL Seguros: carga beneficiarios reales de los regímenes especiales desde el
backup (excombatientes de Malvinas, subsidio de protección a la familia).

Uso:
    DATABASE_URL=sqlite+pysqlite:///./ccypp_real.db \
    python3 -m app.etl.cargar_seguros "/ruta/a/bases"
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal, InvalidOperation

from app.core.database import SessionLocal
from app.etl.dbf import DbfReader
from app import models


def D(v, default="0"):
    try:
        return Decimal(str(v)) if v not in (None, "") else Decimal(default)
    except (InvalidOperation, ValueError):
        return Decimal(default)


def S(v):
    return (str(v).strip() if v is not None else "")


def I(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _regimen(db, contiene):
    return db.query(models.RegimenEspecial).filter(
        models.RegimenEspecial.nombre.like(f"%{contiene}%")).first()


def cargar(bases: str):
    db = SessionLocal()
    seg = os.path.join(bases, "Seguros")

    # ---- Excombatientes de Malvinas (excombate.dbf) ----
    reg = _regimen(db, "Excombatientes")
    p = os.path.join(seg, "excombate.dbf")
    if reg and os.path.exists(p) and not db.query(models.Beneficiario).filter_by(
            regimen_id=reg.id).first():
        n = 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                nombre = S(x.get("nombre"))
                if not nombre:
                    continue
                db.add(models.Beneficiario(
                    regimen_id=reg.id, apellido_nombre=nombre[:80],
                    cuil=S(x.get("cuil"))[:11], dni=S(x.get("dni"))[:9],
                    monto_mensual=reg.monto_default,
                    fecha_alta=x.get("fecha_nac") or __import__("datetime").date.today(),
                    estado="V"))
                n += 1
        db.commit()
        print(f"  excombatientes: {n}")

    # ---- Subsidio de Protección a la Familia (subsidio.dbf) ----
    reg = _regimen(db, "Subsidio")
    p = os.path.join(seg, "subsidio.dbf")
    if reg and os.path.exists(p) and not db.query(models.Beneficiario).filter_by(
            regimen_id=reg.id).first():
        n = 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                nombre = S(x.get("benefici"))
                if not nombre:
                    continue
                monto = D(x.get("mon_cuo"))
                db.add(models.Beneficiario(
                    regimen_id=reg.id, apellido_nombre=nombre[:80],
                    dni=S(x.get("dni"))[:9],
                    monto_mensual=monto if monto > 0 else reg.monto_default,
                    fecha_alta=x.get("fecha_pri") or __import__("datetime").date.today(),
                    estado="V"))
                n += 1
        db.commit()
        print(f"  subsidio protección familia: {n}")

    # ---- Seguros del agente público por período (segurosap) ----
    p = os.path.join(seg, "segurosap.dbf")
    if os.path.exists(p) and not db.query(models.SeguroAgente).first():
        batch, total = [], 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                batch.append({
                    "periodo": S(x.get("periodo"))[:6], "cuil": S(x.get("cuil"))[:11],
                    "titular": S(x.get("titular"))[:60],
                    "remuneracion": D(x.get("remuneraci")),
                    "seg_obligatorio": D(x.get("seg_obliga")),
                    "seg_sepelio": D(x.get("seg_sepeli")),
                    "seg_conyuge": D(x.get("seg_conyug")),
                    "seg_adicional": D(x.get("seg_adicio")),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.SeguroAgente, batch)
                    db.commit(); total += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.SeguroAgente, batch); db.commit(); total += len(batch)
        print(f"  seguros del agente: {total}")

    # ---- titulares del seguro de vida colectivo (titulares) ----
    p = os.path.join(seg, "titulares.dbf")
    if os.path.exists(p) and not db.query(models.TitularSeguro).first():
        import datetime as _dt
        batch, total = [], 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                fn = x.get("fecha_naci")
                batch.append({
                    "cuil": S(x.get("cuil"))[:11], "apellido_nombre": S(x.get("apenom"))[:80],
                    "tipo_titular": S(x.get("tipo_titul"))[:2],
                    "organo": I(x.get("organo")), "sexo": S(x.get("sexo"))[:1],
                    "no_agente": I(x.get("no_agente")),
                    "fecha_nac": fn if isinstance(fn, _dt.date) and fn.year >= 1900 else None,
                    "domicilio": S(x.get("domicilio"))[:80], "localidad": S(x.get("localidad"))[:40],
                    "cantidad": I(x.get("cantidad"), 1),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.TitularSeguro, batch); db.commit(); total += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.TitularSeguro, batch); db.commit(); total += len(batch)
        print(f"  titulares de seguro: {total}")

    db.close()
    print("ETL seguros OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
