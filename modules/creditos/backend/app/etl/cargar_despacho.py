"""ETL Despacho: modelos, resoluciones/disposiciones y sus beneficiarios (backup real).

Fuente (VFP): Despacho/rtf.dbf (modelos), Despacho/resoluciones.dbf, Despacho/beneficiarios.dbf.
Replica la pantalla de Resolución: Nº correlativo (NRO_RES) + Nº real (NRO_REAL), motivo (COD_MOT),
importe, origen (expediente/nota = ID_TRAMITE/ID_LETRA/ID_NRO/ID_ANO), texto y la grilla de beneficiarios.

Uso:
    DATABASE_URL=sqlite+pysqlite:///./ccypp_real.db python3 -m app.etl.cargar_despacho "/ruta/a/bases"
"""
from __future__ import annotations

import os
import re
import sys
import datetime

from app.core.database import SessionLocal
from app.etl.dbf import DbfReader
from app.etl.rtf import rtf_a_html
from app import models


def S(v):
    return str(v).strip() if v is not None else ""


def I(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def F(v):
    """Decimal/float robusto (IMPORTE puede venir como '0.00' string)."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _anio_ok(d) -> int | None:
    if not hasattr(d, "year"):
        return None
    return d.year if 1980 <= d.year <= 2035 else None


def _origen(x: dict) -> str:
    """Exp./Nota que origina el instrumento: ID_TRAMITE + ID_LETRA + ID_NRO/ID_ANO."""
    letra = (S(x.get("id_tramite")) + S(x.get("id_letra"))).strip()
    nro, ano = I(x.get("id_nro")), I(x.get("id_ano"))
    if nro:
        return (f"{letra} {nro}/{ano}" if ano else f"{letra} {nro}").strip()
    return letra


def cargar(bases: str):
    db = SessionLocal()

    # ---- 1) Modelos de resolución/disposición (rtf.dbf) con su plantilla (memo MODELO) ----
    p = os.path.join(bases, "Despacho", "rtf.dbf")
    if os.path.exists(p) and not db.query(models.ModeloResolucion).first():
        rows = []
        with DbfReader(p) as r:
            for x in r.records():
                x = {k.lower(): v for k, v in x.items()}
                cod = I(x.get("cod_mod"))
                if not cod:
                    continue
                plantilla = rtf_a_html(x.get("modelo") or "")
                rows.append({
                    "tipo_res": I(x.get("tipo_res")), "codigo": cod,
                    "descripcion": S(x.get("des_mod"))[:120],
                    "es_disposicion": bool(x.get("disposicio")),
                    "es_seguros": bool(x.get("seguros")),
                    "tiene_plantilla": len(plantilla) > 0,
                    "plantilla": plantilla[:20000],
                })
        db.bulk_insert_mappings(models.ModeloResolucion, rows)
        db.commit()
        print(f"  modelos de resolución: {len(rows)}")

    # No hay tabla de MOTIVOS: COD_MOT es el código del MODELO (rtf.cod_mod) y el "motivo" que muestra la
    # pantalla es la descripción del modelo (ej. 103 → TRANSFERENCIA). Resolvemos la etiqueta desde el catálogo.
    motmap: dict[int, str] = {c: (d or "") for c, d in
                              db.query(models.ModeloResolucion.codigo, models.ModeloResolucion.descripcion).all()}

    # ---- 2) Resoluciones (resoluciones.dbf) ----
    if db.query(models.Resolucion).first():
        print("  ya hay resoluciones; omito resoluciones y beneficiarios")
        return
    p = os.path.join(bases, "Despacho", "resoluciones.dbf")
    if not os.path.exists(p):
        print("  no se encontró resoluciones.dbf")
        return

    # id_resol_por_clave: (numero, anio, tipo) -> pos en `rows` (para linkear beneficiarios luego).
    rows, vistos = [], {}
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            nro = I(x.get("nro_res"))
            fec = x.get("fec_res")
            anio = _anio_ok(fec)
            if not nro or anio is None:
                continue
            dispo = bool(x.get("disposicio"))
            tipo = "DIS" if dispo else "RES"
            clave = (nro, anio, tipo)
            if clave in vistos:                 # correlativo único por (año, tipo): 1ª ocurrencia gana
                continue
            vistos[clave] = len(rows)
            nreal = I(x.get("nro_real")) or None
            freal = x.get("fec_real"); freal = freal if isinstance(freal, datetime.date) else None
            texto = rtf_a_html(x.get("texto") or "")
            plano = re.sub(r"<[^>]+>", " ", texto).strip()   # para asunto: sin tags HTML
            motivo = motmap.get(I(x.get("cod_mot")), "")[:120]
            rows.append({
                "numero": nro, "anio": anio, "tipo": tipo,
                "fecha": fec if isinstance(fec, datetime.date) else datetime.date(anio, 1, 1),
                "numero_real": nreal, "fecha_real": freal,
                "organo": "", "asunto": (motivo or plano[:120] or f"{tipo} {nro}/{anio}"),
                "motivo_cod": I(x.get("cod_mot")), "motivo": motivo,
                "importe": F(x.get("importe")),
                "modelo_codigo": I(x.get("cod_mot")) or None,   # COD_MOT == código del modelo usado
                "origen": _origen(x)[:40],
                "nro_op": I(x.get("nro_op")) or None,
                "texto": texto[:20000],
                "estado": "F", "anulada": bool(x.get("lanulada")),
            })
    B = 5000
    for i in range(0, len(rows), B):
        db.bulk_insert_mappings(models.Resolucion, rows[i:i + B])
        db.commit()
    print(f"  resoluciones: {len(rows)}")

    # id real asignado por la DB: recuperar (numero, anio, tipo) -> id
    idmap: dict[tuple, int] = {}
    for rid, num, an, tp in db.query(models.Resolucion.id, models.Resolucion.numero,
                                     models.Resolucion.anio, models.Resolucion.tipo).all():
        idmap[(num, an, tp)] = rid

    # ---- 3) Beneficiarios (beneficiarios.dbf) linkeados por (NRO_RES, año(FEC_RES), tipo) ----
    p = os.path.join(bases, "Despacho", "beneficiarios.dbf")
    if not os.path.exists(p):
        print("  no se encontró beneficiarios.dbf; sólo resoluciones")
        print("ETL despacho OK")
        return
    bene, sin_match = [], 0
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            nro = I(x.get("nro_res"))
            anio = _anio_ok(x.get("fec_res"))
            if not nro or anio is None:
                continue
            tipo = "DIS" if bool(x.get("disposicio")) else "RES"
            rid = idmap.get((nro, anio, tipo)) or idmap.get((nro, anio, "RES")) or idmap.get((nro, anio, "DIS"))
            if not rid:
                sin_match += 1
                continue
            bene.append({
                "resolucion_id": rid, "tipo_doc": I(x.get("tipo_doc")),
                "nro_doc": S(x.get("nro_doc"))[:11], "nombre": S(x.get("nombre"))[:80],
                "tipo_bene": I(x.get("tipo_bene")),
            })
    for i in range(0, len(bene), B):
        db.bulk_insert_mappings(models.ResolucionBeneficiario, bene[i:i + B])
        db.commit()
    print(f"  beneficiarios: {len(bene)} (sin resolución asociada: {sin_match})")
    print("ETL despacho OK")


if __name__ == "__main__":
    cargar(sys.argv[1])
