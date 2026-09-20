"""ETL Juegos/Quiniela: agencias (agenjuegos) y liquidaciones (cajaliq) reales.

Uso:
    DATABASE_URL=sqlite+pysqlite:///./ccypp_real.db \
    python3 -m app.etl.cargar_juegos "/ruta/a/bases"
"""
from __future__ import annotations

import os
import sys
import datetime
from decimal import Decimal, InvalidOperation

from app.core.database import SessionLocal
from app.etl.dbf import DbfReader
from app import models

MAX_LIQ = 60000   # tope de liquidaciones a cargar (las más recientes por archivo)


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
    return bool(v)


def S(v):
    return str(v).strip() if v is not None else ""


def cargar(bases: str):
    db = SessionLocal()
    caja = os.path.join(bases, "Caja")
    juegos_dir = os.path.join(bases, "Juegos")

    # ---- Maestro de juegos (maejuegos) ----
    p = os.path.join(juegos_dir, "maejuegos.dbf")
    if os.path.exists(p) and not db.query(models.Juego).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                rows.append({
                    "codigo": I(x.get("codigo")), "modalidad": I(x.get("modalidad")),
                    "cod_afip": I(x.get("ncodafip")),
                    "denominacion": S(x.get("denominaci"))[:40],
                    "com_agencia": D(x.get("com_agenci")),
                    "com_subagencia": D(x.get("com_subage")),
                })
        db.bulk_insert_mappings(models.Juego, rows)
        db.commit()
        print(f"  maestro de juegos: {len(rows)}")

    # ---- Sorteos / jugadas (maejugadas) ----
    p = os.path.join(juegos_dir, "maejugadas.dbf")
    if os.path.exists(p) and not db.query(models.Sorteo).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                fs, fv = x.get("fecha_sort"), x.get("fecha_vto")
                rows.append({
                    "cod_juego": I(x.get("cod_juego")), "no_sorteo": I(x.get("no_sorteo")),
                    "fecha_sorteo": fs if isinstance(fs, datetime.date) else None,
                    "fecha_vto": fv if isinstance(fv, datetime.date) else None,
                    "importado_caja": B(x.get("cajaimport")),
                })
        db.bulk_insert_mappings(models.Sorteo, rows)
        db.commit()
        print(f"  sorteos: {len(rows)}")

    # ---- Agencias (agenjuegos) ----
    p = os.path.join(caja, "agenjuegos.dbf")
    if os.path.exists(p) and not db.query(models.AgenciaJuego).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                rows.append({
                    "numero": I(x.get("no_agencia")), "subagencia": I(x.get("no_subagen")),
                    "codigo": I(x.get("cod_agenci")), "interior": B(x.get("interior")),
                    "quiniela": B(x.get("quiniela")), "quini6": B(x.get("quini6")),
                    "loto": B(x.get("loto")), "brinco": B(x.get("brinco")),
                    "prode": B(x.get("prode")), "telekino": B(x.get("telekino")),
                    "activa": True,
                })
        db.bulk_insert_mappings(models.AgenciaJuego, rows)
        db.commit()
        print(f"  agencias: {len(rows)}")

    # ---- Liquidaciones (cajaliq) ----
    p = os.path.join(caja, "cajaliq.dbf")
    if os.path.exists(p) and not db.query(models.LiquidacionAgencia).first():
        batch, total = [], 0
        with DbfReader(p) as r:
            for x in r.records():
                if total >= MAX_LIQ:
                    break
                x = {k.lower(): v for k, v in x.items()}
                fs = x.get("fecha_sort")
                fp = x.get("fecha_pago")
                batch.append({
                    "cod_agencia": I(x.get("cod_agenci")),
                    "no_agencia": I(x.get("no_agencia")), "subagencia": I(x.get("no_subagen")),
                    "cod_juego": I(x.get("cod_juego")),
                    "juego": S(x.get("cjuego"))[:30], "no_sorteo": I(x.get("no_sorteo")),
                    "fecha_sorteo": fs if isinstance(fs, datetime.date) else None,
                    "interior": B(x.get("interior")),
                    "moneda": (S(x.get("moneda")) or "$")[:1],
                    "recaudacion": D(x.get("recaudacio")), "premios": D(x.get("premios")),
                    "com_premios": D(x.get("com_premio")),
                    "comision_agencia": D(x.get("com_agenci")),
                    "comision_subagencia": D(x.get("com_subage")),
                    "multas": D(x.get("multas")),
                    "ing_brutos": D(x.get("ing_brutos")), "fdo_gtia": D(x.get("fdo_gtia")),
                    "total": D(x.get("total")),
                    "intereses": D(x.get("intereses")), "iva": D(x.get("iva")),
                    "total_gral": D(x.get("total_gral")),
                    "fecha_vto": x.get("fecha_vto") if isinstance(x.get("fecha_vto"), datetime.date) else None,
                    "pagado": B(x.get("pagado")),
                    "fecha_pago": fp.date() if isinstance(fp, datetime.datetime) else (fp if isinstance(fp, datetime.date) else None),
                    "cajero": S(x.get("cajero"))[:20], "no_recibo": I(x.get("no_recibo")),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.LiquidacionAgencia, batch)
                    db.commit(); total += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.LiquidacionAgencia, batch); db.commit(); total += len(batch)
        print(f"  liquidaciones: {total}")

    # ---- Recibos de cobro de agencia (cajapagos) ----
    p = os.path.join(caja, "cajapagos.dbf")
    if os.path.exists(p) and not db.query(models.CajaPagoAgencia).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                fp = x.get("fecha_pago")
                rows.append({
                    "cod_agencia": I(x.get("cod_agenci")),
                    "fecha_pago": fp.date() if isinstance(fp, datetime.datetime) else (fp if isinstance(fp, datetime.date) else None),
                    "origen": S(x.get("origen"))[:4] or "JUEG",
                    "no_recibo": I(x.get("no_recibo")),
                    "bonos": D(x.get("bonos")), "pesos": D(x.get("pesos")),
                    "total": D(x.get("total")),
                    "cobrado_bonos": D(x.get("cobrado_bo")), "cobrado_pesos": D(x.get("cobrado_pe")),
                    "cobrado_total": D(x.get("cobrado_to")),
                    "vuelto_bonos": D(x.get("vuelto_bon")), "vuelto_pesos": D(x.get("vuelto_pes")),
                    "premios_bonos": D(x.get("premios_bo")), "premios_pesos": D(x.get("premios_pe")),
                    "cajero": S(x.get("cajero"))[:20], "anulado": B(x.get("anulado")),
                })
        db.bulk_insert_mappings(models.CajaPagoAgencia, rows)
        db.commit()
        print(f"  recibos de agencia (cajapagos): {len(rows)}")

    # ---- Cola/cobros de créditos-seguros-extra (cajacreseg) ----
    p = os.path.join(caja, "cajacreseg.dbf")
    if os.path.exists(p) and not db.query(models.CajaCreSeg).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                fp = x.get("fecha_pago")
                rows.append({
                    "origen": S(x.get("origen"))[:4], "no_credito": I(x.get("no_credito")),
                    "cuil": S(x.get("cuil"))[:11], "dni": S(x.get("dni"))[:9],
                    "apellido_nombre": S(x.get("apenom"))[:80], "cuota": I(x.get("cualcuo")),
                    "moncuo": D(x.get("moncuo")), "interes": D(x.get("interes")),
                    "iva_interes": D(x.get("ivain")), "seguro": D(x.get("nseg")),
                    "iva_seguro": D(x.get("nivaseg")), "gastos": D(x.get("gastos")),
                    "iva_gastos": D(x.get("nivaadm")),
                    "interes_punit": D(x.get("intereses")), "iva_punit": D(x.get("iva")),
                    "total": D(x.get("total")), "total_gral": D(x.get("total_gral")),
                    "moneda": (S(x.get("moneda")) or "$")[:1], "cajero": S(x.get("cajero"))[:20],
                    "fecha_pago": fp.date() if isinstance(fp, datetime.datetime) else (fp if isinstance(fp, datetime.date) else None),
                    "pagado": B(x.get("pagado")), "revertida": B(x.get("lrevertida")),
                    "no_recibo": I(x.get("recofi")), "mes": I(x.get("mes")), "ano": I(x.get("ano")),
                    "coding": I(x.get("coding")), "subing": I(x.get("subing")),
                    "ctactble": S(x.get("ctactble"))[:20],
                })
        db.bulk_insert_mappings(models.CajaCreSeg, rows)
        db.commit()
        print(f"  cola créditos/seguros/extra (cajacreseg): {len(rows)}")
    print("ETL juegos OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
