"""ETL Mesa de Entradas: catálogo de tipos (tipotram) y trámites (tramites).

Uso: python -m app.etl.cargar_tramites "/ruta/a/bases"
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


def _fecha(v):
    if isinstance(v, datetime.datetime):
        v = v.date()
    if isinstance(v, datetime.date) and v.year >= 1990:
        return v
    return None


def cargar(bases: str):
    db = SessionLocal()
    mesa = os.path.join(bases, "Mesa")
    general = os.path.join(bases, "General")

    # ---- oficinas (General/oficinas) ----
    p = os.path.join(general, "oficinas.dbf")
    if os.path.exists(p) and not db.query(models.Oficina).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                oid = I(x.get("id_oficina"))
                if not oid:
                    continue
                rows.append({"id": oid, "denominacion": S(x.get("denominaci"))[:60],
                             "telefono_interno": S(x.get("te_interno"))[:10],
                             "telefono_linea": S(x.get("te_linea"))[:20],
                             "interna": bool(x.get("interna"))})
        db.bulk_insert_mappings(models.Oficina, rows)
        db.commit()
        print(f"  oficinas: {len(rows)}")

    # ---- perfiles (General/maeperfil) ----
    p = os.path.join(general, "maeperfil.dbf")
    if os.path.exists(p) and not db.query(models.Perfil).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                cod = S(x.get("cod_perfil"))[:6]
                if not cod:
                    continue
                rows.append({"codigo": cod, "denominacion": S(x.get("denominaci"))[:60],
                             "habilitado": bool(x.get("habilitado"))})
        db.bulk_insert_mappings(models.Perfil, rows)
        db.commit()
        print(f"  perfiles: {len(rows)}")

    # ---- proveedores (General/proveedores) ----
    p = os.path.join(general, "proveedores.dbf")
    if os.path.exists(p) and not db.query(models.Proveedor).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                nid = I(x.get("nproveedor"))
                if not nid:
                    continue
                rows.append({
                    "id": nid, "cuit": S(x.get("cuit"))[:11],
                    "razon_social": S(x.get("crazonsoc"))[:80], "contacto": S(x.get("contacto"))[:60],
                    "domicilio": S(x.get("cdomicilio"))[:80], "localidad": S(x.get("clocalidad"))[:40],
                    "departamento": S(x.get("cdepto"))[:40], "tipo_iva": S(x.get("ctipoiva"))[:4],
                    "ingresos_brutos": S(x.get("niibb"))[:15], "anulado": bool(x.get("lanulado")),
                })
        db.bulk_insert_mappings(models.Proveedor, rows)
        db.commit()
        print(f"  proveedores: {len(rows)}")

    # ---- tipos de trámite (tipotram) ----
    p = os.path.join(mesa, "tipotram.dbf")
    if os.path.exists(p) and not db.query(models.TramiteTipo).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                rows.append({"codigo": S(x.get("tipo"))[:4],
                             "descripcion": S(x.get("descripcio"))[:60],
                             "corta": S(x.get("des_red"))[:15]})
        db.bulk_insert_mappings(models.TramiteTipo, rows)
        db.commit()
        print(f"  tipos de trámite: {len(rows)}")

    # ---- trámites (tramites) ----
    p = os.path.join(mesa, "tramites.dbf")
    if os.path.exists(p) and not db.query(models.Tramite).first():
        batch, total = [], 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                batch.append({
                    "tipo": S(x.get("id_tramite"))[:4], "letra": S(x.get("id_letra"))[:2],
                    "numero": I(x.get("id_nro")), "anio": I(x.get("id_ano")),
                    "sentido": S(x.get("i_d"))[:1],
                    "referencia": S(x.get("referencia"))[:120],
                    "iniciador": (S(x.get("nombre_ini")) or S(x.get("iniciador")))[:80],
                    "asegurado": S(x.get("nombre_ase"))[:80],
                    "destino": S(x.get("destino"))[:40],
                    "estado": S(x.get("estado"))[:1], "oficina_actual": I(x.get("oficina_ac")),
                    "hojas": I(x.get("ncanhojas")), "fecha_alta": _fecha(x.get("fecha_alta")),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.Tramite, batch); db.commit(); total += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.Tramite, batch); db.commit(); total += len(batch)
        print(f"  trámites: {total}")

    # ---- pases (pases) ----
    p = os.path.join(mesa, "pases.dbf")
    if os.path.exists(p) and not db.query(models.TramitePase).first():
        batch, total = [], 0
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                batch.append({
                    "tipo": S(x.get("id_tramite"))[:4], "letra": S(x.get("id_letra"))[:2],
                    "numero": I(x.get("id_nro")), "anio": I(x.get("id_ano")),
                    "fecha_pase": _fecha(x.get("fecha_pase")),
                    "oficina_origen": I(x.get("oficina_or")), "oficina_destino": I(x.get("oficina_de")),
                    "texto": S(x.get("texto"))[:255], "activo": bool(x.get("activo")),
                })
                if len(batch) >= 5000:
                    db.bulk_insert_mappings(models.TramitePase, batch); db.commit(); total += len(batch); batch = []
        if batch:
            db.bulk_insert_mappings(models.TramitePase, batch); db.commit(); total += len(batch)
        print(f"  pases: {total}")

    db.close()
    print("ETL trámites OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
