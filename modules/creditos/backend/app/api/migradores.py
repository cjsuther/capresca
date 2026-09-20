"""Panel de migradores DBF → modelo. Restringido a Administrador (ADMG).

Permite ver el catálogo (programa VFP, DBF, tabla, conversiones, conteos) y
**ejecutar / re-ejecutar** cada migración contra los .dbf del sistema legacy.
Las corridas se hacen en segundo plano y su estado se consulta por polling.
"""
from __future__ import annotations

import threading
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import requiere_perfil
from app.etl import registro

router = APIRouter(prefix="/api/creditos/migradores", tags=["migradores"],
                   dependencies=[Depends(requiere_perfil("AD"))])  # ADMG

# Estado de corridas en memoria: clave -> {estado, filas, mensaje, ts}
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _set(clave: str, **kw):
    with _LOCK:
        _JOBS[clave] = {**_JOBS.get(clave, {}), **kw, "ts": time.time()}


def _correr(clave: str, reset: bool):
    _set(clave, estado="corriendo", mensaje="", filas=None)
    try:
        r = registro.ejecutar(clave, reset=reset)
        _set(clave, estado="ok", filas=r["migrados"], mensaje=f"{r['migrados']} registros")
    except Exception as e:  # noqa: BLE001
        _set(clave, estado="error", mensaje=str(e)[:300])


def _correr_todo(reset: bool):
    _set("__todo__", estado="corriendo", mensaje="", filas=None)
    hechos = 0
    try:
        for m in registro.REGISTRO:
            _set(m.clave, estado="corriendo", mensaje="", filas=None)
            try:
                r = registro.ejecutar(m.clave, reset=reset)
                _set(m.clave, estado="ok", filas=r["migrados"], mensaje=f"{r['migrados']} registros")
                hechos += 1
            except Exception as e:  # noqa: BLE001
                _set(m.clave, estado="error", mensaje=str(e)[:300])
        _set("__todo__", estado="ok", mensaje=f"{hechos}/{len(registro.REGISTRO)} migradores OK")
    except Exception as e:  # noqa: BLE001
        _set("__todo__", estado="error", mensaje=str(e)[:300])


@router.get("")
def catalogo(db: Session = Depends(get_db)):
    """Catálogo de migradores con conteos y estado de la última corrida."""
    items = registro.estado(db)
    with _LOCK:
        for it in items:
            it["job"] = _JOBS.get(it["clave"])
        todo = _JOBS.get("__todo__")
    return {"items": items, "bases": registro.BASES, "todo": todo}


@router.post("/{clave}/ejecutar")
def ejecutar(clave: str, reset: bool = False):
    """Ejecuta (o re-ejecuta con reset) un migrador en segundo plano."""
    if clave not in registro.REGISTRO_POR_CLAVE:
        raise HTTPException(404, f"Migrador '{clave}' inexistente")
    with _LOCK:
        actual = _JOBS.get(clave)
    if actual and actual.get("estado") == "corriendo":
        raise HTTPException(409, "Ese migrador ya está corriendo")
    threading.Thread(target=_correr, args=(clave, reset), daemon=True).start()
    return {"estado": "iniciado", "clave": clave, "reset": reset}


@router.get("/inventario")
def inventario():
    """Inventario de todos los .dbf del backup por carpeta: cuáles se migran (a qué
    tabla) y cuáles no, con nº de registros y campos de cada uno."""
    return registro.inventario()


@router.get("/esquema")
def esquema():
    """Esquema para el DER: modelo actual (tablas + columnas + FKs reales) y los
    DBFs legacy (campos por migrador). Sirve para comparar el modelo nuevo contra
    el origen VFP."""
    from app.core.database import Base

    # Módulo y origen legacy por tabla (desde el registro).
    tabla_modulo: dict[str, str] = {}
    tabla_origen: dict[str, str] = {}
    for m in registro.REGISTRO:
        for t in (m.tablas or [m.tabla]):
            tabla_modulo.setdefault(t, m.modulo)
            tabla_origen.setdefault(t, m.dbf)
    tabla_modulo.update(registro.MODULO_EXTRA)

    actual = []
    for nombre, t in Base.metadata.tables.items():
        cols = []
        for c in t.columns:
            fk = None
            if c.foreign_keys:
                destino = next(iter(c.foreign_keys)).column
                fk = {"tabla": destino.table.name, "columna": destino.name}
            cols.append({"nombre": c.name, "tipo": str(c.type).split("(")[0],
                         "pk": bool(c.primary_key), "fk": fk})
        actual.append({"tabla": nombre, "modulo": tabla_modulo.get(nombre, "Otros"),
                       "origen": tabla_origen.get(nombre),   # None = se genera en la app
                       "usos": registro.usos(nombre),        # pantallas del menú que la usan
                       "columnas": cols})
    actual.sort(key=lambda x: (x["modulo"], x["tabla"]))

    legacy = [{
        "clave": m.clave, "modulo": m.modulo, "nombre": m.nombre,
        "dbf": m.dbf, "tabla_destino": m.tabla,
        "campos": [{"origen": o, "destino": d, "tipo": t} for o, d, t in m.conversiones],
    } for m in registro.REGISTRO]

    return {"actual": actual, "legacy": legacy}


@router.post("/ejecutar-todo")
def ejecutar_todo(reset: bool = False):
    """Ejecuta todos los migradores en orden de dependencias, en segundo plano."""
    with _LOCK:
        actual = _JOBS.get("__todo__")
    if actual and actual.get("estado") == "corriendo":
        raise HTTPException(409, "Ya hay una migración total en curso")
    threading.Thread(target=_correr_todo, args=(reset,), daemon=True).start()
    return {"estado": "iniciado", "reset": reset}
