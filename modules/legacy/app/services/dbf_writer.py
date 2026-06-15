"""
Escritura en DBF — Fase 4, modo SANDBOX.

Escribe SIEMPRE bajo `settings.sandbox_write_root` (una COPIA), nunca el share
productivo (montado read-only). La librería `dbf` (Ethan Furman) NO mantiene los
índices .CDX; por eso el modo productivo queda fuera de alcance hasta disponer de
un REINDEX en VFP. Acá solo se prueba la mecánica INSERT/REPLACE.

Hace backup de las DBF objetivo antes de tocarlas y es idempotente por no_recibo.
"""
import os
import shutil
from datetime import datetime, date

import dbf

from app.config import settings
from app.legacy_catalog import relative_path


def _path(table: str) -> str:
    rel = relative_path(table)
    if rel is None:
        raise ValueError(f"Tabla desconocida: {table}")
    return os.path.join(settings.sandbox_write_root, rel)


def _to_legacy_date(s) -> str:
    """ISO 'YYYY-MM-DD' (o date) -> 'DD/MM/YYYY' como guarda el legacy."""
    if not s:
        return ""
    if isinstance(s, date):
        d = s
    else:
        try:
            d = datetime.strptime(str(s), "%Y-%m-%d").date()
        except ValueError:
            return str(s)
    return d.strftime("%d/%m/%Y")


def _backup(paths: list[str]) -> str | None:
    existing = [p for p in paths if os.path.isfile(p)]
    if not existing:
        return None
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(settings.sandbox_write_root, "_backup", stamp)
    os.makedirs(dest, exist_ok=True)
    for p in existing:
        shutil.copy2(p, os.path.join(dest, os.path.basename(p)))
        # incluir memo .fpt si existiera
        fpt = p[:-4] + ".fpt"
        if os.path.isfile(fpt):
            shutil.copy2(fpt, os.path.join(dest, os.path.basename(fpt)))
    return dest


def _open(table: str):
    path = _path(table)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"DBF sandbox no encontrada: {path}")
    t = dbf.Table(path)
    t.open(dbf.READ_WRITE)
    return t


def _recibo_existe(payload_no_recibo) -> bool:
    t = _open("cajapagos")
    try:
        target = str(payload_no_recibo).strip()
        for rec in t:
            if str(rec.NO_RECIBO).strip() == target:
                return True
        return False
    finally:
        t.close()


def apply_aplicar_pago(payload: dict) -> dict:
    """INSERT cajapagos + cajaforpag y REPLACE cajaliq.pagado. Idempotente por no_recibo."""
    no_recibo = payload["no_recibo"]
    if _recibo_existe(no_recibo):
        return {"status": "SKIPPED", "reason": f"no_recibo {no_recibo} ya existe en cajapagos"}

    _backup([_path("cajapagos"), _path("cajaforpag"), _path("cajaliq")])
    rows = {"cajapagos": 0, "cajaforpag": 0, "cajaliq": 0}
    fecha = _to_legacy_date(payload.get("fecha_pago"))

    # cajapagos
    t = _open("cajapagos")
    try:
        t.append({
            "NO_RECIBO": str(no_recibo),
            "COD_AGEN": str(payload.get("cod_agencia") or ""),
            "FECHA_PAGO": fecha,
            "ORIGEN": str(payload.get("origen") or ""),
            "TOTAL": str(payload.get("total") or "0"),
            "BONOS": "0",
            "PESOS": str(payload.get("total") or "0"),
            "CAJERO": str(payload.get("cajero") or ""),
        })
        rows["cajapagos"] += 1
    finally:
        t.close()

    # cajaforpag
    formas = payload.get("formas_pago") or []
    if formas:
        t = _open("cajaforpag")
        try:
            for i, fp in enumerate(formas, start=1):
                t.append({
                    "NO_RECIBO": str(no_recibo),
                    "SNO_RECIBO": str(fp.get("sno_recibo") or i),
                    "MONEDA": str(fp.get("moneda") or "$"),
                    "ORIGEN": str(fp.get("origen") or ""),
                    "FECHA_PAGO": fecha,
                    "ANULADO": False,
                })
                rows["cajaforpag"] += 1
        finally:
            t.close()

    # cajaliq: marcar pagadas las liquidaciones indicadas
    liqs = payload.get("liquidaciones") or []
    if liqs:
        keys = {(str(l.get("cod_agencia")).strip(), str(l.get("cod_juego")).strip(), str(l.get("no_sorteo")).strip()) for l in liqs}
        t = _open("cajaliq")
        try:
            for rec in t:
                k = (str(rec.COD_AGEN).strip(), str(rec.COD_JUEGO).strip(), str(rec.NO_SORTEO).strip())
                if k in keys:
                    dbf.write(rec, PAGADO=True, FECHA_PAGO=fecha, NO_RECIBO=str(no_recibo))
                    rows["cajaliq"] += 1
        finally:
            t.close()

    return {"status": "APPLIED", "rows": rows}


def apply_anular_pago(payload: dict) -> dict:
    """REPLACE cajaforpag.anulado=True y revertir cajaliq.pagado para el no_recibo."""
    no_recibo = str(payload["no_recibo"]).strip()
    _backup([_path("cajaforpag"), _path("cajaliq")])
    rows = {"cajaforpag": 0, "cajaliq": 0}

    t = _open("cajaforpag")
    try:
        for rec in t:
            if str(rec.NO_RECIBO).strip() == no_recibo:
                dbf.write(rec, ANULADO=True)
                rows["cajaforpag"] += 1
    finally:
        t.close()

    t = _open("cajaliq")
    try:
        for rec in t:
            if str(rec.NO_RECIBO).strip() == no_recibo:
                dbf.write(rec, PAGADO=False, NO_RECIBO="")
                rows["cajaliq"] += 1
    finally:
        t.close()

    return {"status": "APPLIED", "rows": rows}


# operación -> handler
HANDLERS = {
    "aplicar_pago": apply_aplicar_pago,
    "anular_pago": apply_anular_pago,
}
