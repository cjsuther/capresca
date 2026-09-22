"""ETL: muestra del log de auditoría real (General/auditoria, 6,5M registros).

Se carga una muestra acotada (las últimas MAX filas) para la consulta.

Uso:
    DATABASE_URL=... python3 -m app.etl.cargar_auditoria "/bases"
"""
from __future__ import annotations

import os
import sys
import datetime
from collections import deque

from app.core.database import SessionLocal
from app.etl.dbf import DbfReader
from app import models

MAX = 50000   # últimas N filas


def S(v):
    return str(v).strip() if v is not None else ""


def cargar(bases: str):
    db = SessionLocal()
    if db.query(models.EventoAuditoria).first():
        print("  ya hay eventos de auditoría; omito")
        return
    p = os.path.join(bases, "General", "auditoria.dbf")
    if not os.path.exists(p):
        print("  no se encontró auditoria.dbf")
        return

    # quedarnos con las últimas MAX filas sin cargar todo en memoria
    ultimos = deque(maxlen=MAX)
    with DbfReader(p) as r:
        for x in r.records():
            x = {k.lower(): v for k, v in x.items()}
            he = x.get("hora_event")
            ultimos.append({
                "fecha_hora": he if isinstance(he, datetime.datetime) else None,
                "maquina": S(x.get("maquina"))[:40], "usuario": S(x.get("usuario"))[:40],
                "sistema": S(x.get("csistema"))[:20], "perfil": S(x.get("cperfil"))[:8],
                "proceso": S(x.get("proceso"))[:60], "opcion": S(x.get("opcion"))[:80],
            })

    rows = [r for r in ultimos]
    B, total = 5000, 0
    for i in range(0, len(rows), B):
        db.bulk_insert_mappings(models.EventoAuditoria, rows[i:i + B])
        db.commit(); total += len(rows[i:i + B])
    print(f"  eventos de auditoría (muestra): {total}")
    print("ETL auditoría OK")


if __name__ == "__main__":
    cargar(sys.argv[1] if len(sys.argv) > 1 else "/bases")
