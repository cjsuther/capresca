"""Regla de aprobación de los lotes (workflow de Configuraciones, módulo `tesoreria`, objeto LOTE_PAGO).

La definición (niveles, rol que aprueba cada uno, cuatro-ojos, excepciones por usuario) vive en
Configuraciones; la ejecución (quién aprobó qué nivel de qué lote) vive acá, con la DB como árbitro.
Si Configuraciones no responde no se aprueba nada (falla cerrado): no se puede saltear el control.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx
from fastapi import HTTPException

from app.config import settings

OBJETO = "LOTE_PAGO"
# Rol del nivel → permiso de Seguridad (acción del módulo `tesoreria`).
ROLES = {"APROBAR": "aprobaciones:aprobar", "SUPERVISAR": "aprobaciones:supervisar"}
_CACHE_SEGUNDOS = 30
_cache: dict[str, tuple[float, "Regla | None"]] = {}


@dataclass(frozen=True)
class Nivel:
    orden: int
    nombre: str
    rol: str
    cuatro_ojos: bool
    incluidos: frozenset[str] = frozenset()
    excluidos: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Regla:
    activo: bool
    niveles: list[Nivel] = field(default_factory=list)


def _leer_http() -> dict | None:
    r = httpx.get(f"{settings.configuraciones_service_url.rstrip('/')}/internal/configuraciones/workflow/tesoreria/{OBJETO}",
                  headers={"X-Api-Key": settings.configuraciones_internal_api_key}, timeout=5.0)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


_fuente = _leer_http


def usar_fuente(f) -> None:
    """Los tests reemplazan la lectura HTTP por una en memoria."""
    global _fuente
    _fuente = f
    _cache.clear()


def regla() -> Regla | None:
    ahora = time.monotonic()
    en_cache = _cache.get(OBJETO)
    if en_cache and ahora - en_cache[0] < _CACHE_SEGUNDOS:
        return en_cache[1]
    try:
        d = _fuente()
    except Exception as e:
        if en_cache:
            return en_cache[1]
        raise HTTPException(503, f"No se pudo leer el workflow de aprobación (Configuraciones): {e}")
    r = None
    if d:
        niveles = []
        for n in sorted(d.get("niveles", []), key=lambda x: x["orden"]):
            us = n.get("usuarios", [])
            niveles.append(Nivel(orden=n["orden"], nombre=n.get("nombre", ""), rol=(n.get("rol") or "").upper(),
                                 cuatro_ojos=bool(n.get("cuatroOjos", True)),
                                 incluidos=frozenset(u["username"] for u in us if u.get("modo") == "INCLUIR"),
                                 excluidos=frozenset(u["username"] for u in us if u.get("modo") == "EXCLUIR")))
        r = Regla(activo=bool(d.get("activo")), niveles=niveles)
    _cache[OBJETO] = (ahora, r)
    return r


def habilitado(nivel: Nivel, username: str, permisos: frozenset[str]) -> bool:
    if username in nivel.excluidos:
        return False
    if username in nivel.incluidos:
        return True
    permiso = ROLES.get(nivel.rol)
    return bool(permiso) and f"tesoreria:{permiso}" in permisos
