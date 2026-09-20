"""ETL: reconstruye el libro diario por PARTIDA DOBLE (asientos + asientos_lineas)
a partir del mayor plano ya migrado (movimientos_contables ← Contabilidad/asientos.dbf).

El asientos.dbf legacy es un mayor plano: cada fila es una pierna (débito o crédito)
y el campo CREFERENCI (referencia) vincula las piernas de un mismo asiento. Se agrupa
por (periodo, fecha, referencia) → una cabecera Asiento con sus líneas.

Depende de que 'contable' (movimientos_contables) esté cargado.

Uso: python -m app.etl.cargar_asientos_pd "/ruta/a/bases"
"""
from __future__ import annotations

import sys
from decimal import Decimal

from sqlalchemy import text

from app.core.database import SessionLocal, engine
from app import models

CERO = Decimal("0")


def cargar(bases: str = ""):
    db = SessionLocal()
    if db.query(models.Asiento).first():
        print("  asientos (partida doble): omito (ya hay asientos)")
        db.close()
        return
    if not db.query(models.MovimientoContable).first():
        print("  asientos (partida doble): omito (falta movimientos_contables — correr 'contable' antes)")
        db.close()
        return

    # Conexión SEPARADA para el cursor de lectura (streaming); los commits de la
    # sesión de escritura no deben invalidar este cursor.
    read_conn = engine.connect().execution_options(stream_results=True, yield_per=20000)
    filas = read_conn.execute(text(
        "SELECT periodo, fecha, referencia, ctaplan, cuenta, debito, credito "
        "FROM movimientos_contables ORDER BY periodo, fecha, referencia"))

    aid = 0
    asientos: list[dict] = []
    lineas: list[dict] = []
    cur_key = None
    cur_fecha = None
    cur_lineas: list[tuple] = []
    total = 0

    def flush(key, fecha, lns):
        nonlocal aid
        aid += 1
        periodo, ref = key[0], key[2]
        asientos.append({
            "id": aid, "fecha": fecha, "origen": "legacy", "ref_id": None,
            "concepto": (str(ref).strip() or f"Asiento {periodo}")[:120],
        })
        for ctaplan, cuenta, deb, cred in lns:
            lineas.append({
                "asiento_id": aid,
                "cuenta_codigo": (str(ctaplan or "").strip())[:12],
                "cuenta_nombre": (str(cuenta or "").strip())[:80],
                "debe": deb or CERO, "haber": cred or CERO,
            })

    def volcar():
        nonlocal total
        if asientos:
            db.bulk_insert_mappings(models.Asiento, asientos)
            db.bulk_insert_mappings(models.AsientoLinea, lineas)
            db.commit()
            total += len(asientos)
            asientos.clear(); lineas.clear()

    import datetime
    for r in filas:
        key = (r.periodo, r.fecha, r.referencia)
        if cur_key is not None and key != cur_key:
            flush(cur_key, cur_fecha or datetime.date(2000, 1, 1), cur_lineas)
            cur_lineas = []
            if len(asientos) >= 5000:
                volcar()
        cur_key = key
        cur_fecha = r.fecha
        cur_lineas.append((r.ctaplan, r.cuenta, r.debito, r.credito))
    if cur_key is not None:
        flush(cur_key, cur_fecha or datetime.date(2000, 1, 1), cur_lineas)
    volcar()

    read_conn.close()
    print(f"  asientos (partida doble): {total} asientos reconstruidos")
    db.close()


if __name__ == "__main__":
    cargar(sys.argv[1] if len(sys.argv) > 1 else "")
