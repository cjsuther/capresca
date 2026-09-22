"""
Migración de la configuración que vivía en Créditos al módulo Configuraciones de Portezuelo.

Impuestos, índices de referencia, feriados y las reglas del workflow de aprobaciones pasaron a ser
del módulo Configuraciones. Este script copia lo que hay en las tablas viejas de Créditos
(`impuestos`, `indices_referencia`, `feriados`, `pp_workflow_regla/_nivel/_nivel_usuario`) con
`POST /internal/configuraciones/importar`, que es idempotente por clave natural: se puede correr
más de una vez. Las tablas viejas no se borran (quedan como respaldo).

Ejecución (una vez, después de levantar Configuraciones):
    docker compose exec creditos python -m app.etl.migrar_configuraciones [--dry-run]
"""
from __future__ import annotations

import argparse
import sys

import httpx
from sqlalchemy import inspect, text

from app.core import configuraciones
from app.core.config import get_settings
from app.core.database import engine

ROLES = {"APROBAR", "SUPERVISAR"}


def _iso(v) -> str | None:
    """Fecha como ISO: Postgres devuelve `date`; otros motores, el texto ya en ISO."""
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def _filas(conn, tabla: str, sql: str) -> list:
    return list(conn.execute(text(sql))) if inspect(conn).has_table(tabla) else []


def leer() -> dict:
    """Arma el lote de importación a partir de las tablas viejas (las que existan)."""
    with engine.connect() as conn:
        impuestos = [{
            "codigo": r.codigo, "nombre": r.nombre, "tipo": r.tipo, "alicuota": float(r.alicuota or 0),
            "base": r.base, "cuenta_contable": r.cuenta_contable or "", "jurisdiccion": r.jurisdiccion or "",
            "vigente_desde": _iso(r.vigente_desde), "vigente_hasta": _iso(r.vigente_hasta),
            "activo": bool(r.activo),
        } for r in _filas(conn, "impuestos", "SELECT * FROM impuestos ORDER BY id")]
        indices = [{
            "codigo": r.codigo, "nombre": r.nombre, "valor": float(r.valor or 0), "fuente": r.fuente or "",
            "fecha_valor": _iso(r.fecha_valor), "activo": bool(r.activo),
        } for r in _filas(conn, "indices_referencia", "SELECT * FROM indices_referencia ORDER BY id")]
        feriados = [{
            "pais": r.pais, "fecha": _iso(r.fecha), "nombre": r.nombre, "tipo": r.tipo,
            "origen": r.origen, "activo": bool(r.activo),
        } for r in _filas(conn, "feriados", "SELECT * FROM feriados ORDER BY pais, fecha")]

        reglas = []
        niveles = _filas(conn, "pp_workflow_nivel", "SELECT * FROM pp_workflow_nivel ORDER BY orden")
        usuarios = _filas(conn, "pp_workflow_nivel_usuario", "SELECT * FROM pp_workflow_nivel_usuario")
        for r in _filas(conn, "pp_workflow_regla", "SELECT * FROM pp_workflow_regla ORDER BY objeto"):
            reglas.append({
                "objeto": r.objeto, "nombre": r.nombre or "", "descripcion": r.descripcion or "",
                "activo": bool(r.activo),
                "niveles": [{
                    "orden": n.orden, "nombre": n.nombre or "Aprobación",
                    # perfiles VFP que hubieran quedado (ADMG, XCR…) ya no son roles: pasan a APROBAR
                    "rol": (n.rol or "").upper() if (n.rol or "").upper() in ROLES else "APROBAR",
                    "cuatro_ojos": bool(n.cuatro_ojos),
                    "usuarios": [{"username": u.username, "modo": u.modo} for u in usuarios if u.nivel_id == n.id],
                } for n in niveles if n.regla_id == r.id],
            })
    return {"modulo": configuraciones.MODULO, "impuestos": impuestos, "indices": indices,
            "feriados": feriados, "workflow": reglas}


def migrar(dry_run: bool = False) -> dict:
    lote = leer()
    resumen = {k: len(v) for k, v in lote.items() if isinstance(v, list)}
    if dry_run:
        return {"dry_run": True, "leidos": resumen}
    s = get_settings()
    r = httpx.post(f"{s.configuraciones_service_url.rstrip('/')}/internal/configuraciones/importar",
                   json=lote, headers={"X-Api-Key": s.configuraciones_internal_api_key}, timeout=120.0)
    r.raise_for_status()
    configuraciones.limpiar_cache()
    return {"leidos": resumen, "importados": r.json()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print(migrar(dry_run=args.dry_run))
    sys.exit(0)
