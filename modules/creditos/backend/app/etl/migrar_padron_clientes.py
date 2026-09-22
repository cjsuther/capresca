"""
Migración del maestro de clientes de CCyPP al PADRÓN de Portezuelo (módulo Clientes).

A partir de esta migración, Créditos no tiene maestro propio: la identidad vive en el módulo
Clientes y la tabla `clientes` de Créditos es un espejo cuyo `id` es el id del padrón.

Qué hace, en una transacción por lote:
  1. Lee el maestro local (clientes).
  2. Lo empuja al padrón (`POST /internal/clientes/importar`, idempotente por documento).
  3. Reescribe las FKs de solicitudes, créditos, recibos y pólizas al id nuevo.
  4. Re-clava las filas espejo con el id del padrón.

Ejecución:
    docker compose exec creditos python -m app.etl.migrar_padron_clientes [--dry-run] [--lote 500]

Es reentrante: los clientes ya migrados (id == id del padrón) se saltean.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from app.core import clientes_padron
from app.core.database import SessionLocal

# Tablas de Créditos que apuntan al cliente.
REFERENCIAS = ("solicitudes", "creditos", "recibos", "polizas")


def _personas(filas) -> list[dict]:
    personas = []
    for c in filas:
        apellido, _, nombres = (c.apellido_nombre or "").partition(",")
        personas.append({
            "documento": (c.cuil or c.dni or "").strip(),
            "tipo_documento": "CUIL" if c.cuil else "DNI",
            "apellido": apellido.strip() or (c.apellido_nombre or "").strip(),
            "nombres": nombres.strip(),
            "email": c.email or "",
            "telefono": c.telefono or "",
            "domicilio": c.domicilio or "",
            "localidad": c.localidad or "",
            "fecha_nacimiento": str(c.fecha_nacimiento) if c.fecha_nacimiento else None,
            "sexo": c.sexo or None,
            "baja": bool(c.baja),
        })
    return personas


def migrar(lote: int = 500, dry_run: bool = False) -> dict:
    db = SessionLocal()
    resumen = {"leidos": 0, "migrados": 0, "sin_documento": 0, "ya_migrados": 0}
    try:
        # `migrado` marca las filas cuyo id ya es el del padrón (reentrancia).
        db.execute(text("CREATE TABLE IF NOT EXISTS clientes_padron_map ("
                        "id_viejo integer PRIMARY KEY, id_padron integer NOT NULL)"))
        db.commit()
        ya = {r[0] for r in db.execute(text("SELECT id_viejo FROM clientes_padron_map"))}

        while True:
            filas = db.execute(text(
                "SELECT id, cuil, dni, apellido_nombre, email, telefono, domicilio, localidad, "
                "       fecha_nacimiento, sexo, baja "
                "FROM clientes WHERE id NOT IN (SELECT id_viejo FROM clientes_padron_map) "
                "ORDER BY id LIMIT :lote"), {"lote": lote}).fetchall()
            if not filas:
                break
            resumen["leidos"] += len(filas)

            personas = _personas(filas)
            sin_doc = [p for p in personas if not p["documento"]]
            resumen["sin_documento"] += len(sin_doc)
            personas = [p for p in personas if p["documento"]]

            if dry_run:
                print(f"[dry-run] {len(personas)} personas listas para el padrón "
                      f"(y {len(sin_doc)} sin documento, que quedan afuera).")
                break

            r = clientes_padron.importar(personas)
            mapeo = {**(r.get("creados") or {}), **(r.get("existentes") or {})}

            for c in filas:
                documento = (c.cuil or c.dni or "").strip()
                nuevo = mapeo.get(documento)
                if not nuevo or int(nuevo) == c.id:
                    if nuevo and int(nuevo) == c.id:
                        resumen["ya_migrados"] += 1
                        db.execute(text("INSERT INTO clientes_padron_map VALUES (:v, :n)"),
                                   {"v": c.id, "n": int(nuevo)})
                    continue
                nuevo = int(nuevo)
                # El espejo nuevo primero (para no violar las FKs), después se mueven las referencias.
                db.execute(text(
                    "INSERT INTO clientes (id, id_cliente, cuil, dni, apellido_nombre, sexo, "
                    "  fecha_nacimiento, domicilio, barrio, localidad, telefono, email, cbu, "
                    "  debito_automatico, sueldo, categoria_funcion, fecha_ingreso, tipo_cliente, "
                    "  baja, fecha_baja, motivo_baja, organismo_id) "
                    "SELECT :nuevo, id_cliente, cuil, dni, apellido_nombre, sexo, fecha_nacimiento, "
                    "  domicilio, barrio, localidad, telefono, email, cbu, debito_automatico, sueldo, "
                    "  categoria_funcion, fecha_ingreso, tipo_cliente, baja, fecha_baja, motivo_baja, "
                    "  organismo_id FROM clientes WHERE id = :viejo "
                    "ON CONFLICT (id) DO NOTHING"), {"nuevo": nuevo, "viejo": c.id})
                for tabla in REFERENCIAS:
                    db.execute(text(f"UPDATE {tabla} SET cliente_id = :nuevo WHERE cliente_id = :viejo"),
                               {"nuevo": nuevo, "viejo": c.id})
                db.execute(text("DELETE FROM clientes WHERE id = :viejo"), {"viejo": c.id})
                db.execute(text("INSERT INTO clientes_padron_map VALUES (:v, :n)"), {"v": c.id, "n": nuevo})
                resumen["migrados"] += 1
            db.commit()
        return resumen
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lote", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    r = migrar(lote=args.lote, dry_run=args.dry_run)
    print(r)
    sys.exit(0)
