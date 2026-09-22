"""
Configuración compartida: vive en el módulo Configuraciones de Portezuelo.

Créditos no guarda impuestos, índices de referencia, feriados ni las reglas del workflow de
aprobaciones: los lee de la API interna de Configuraciones (red de Docker, con clave compartida).

- Caché corta (`configuraciones_cache_segundos`): una simulación en vivo no pega al servicio por
  cada tecla, y un cambio en Configuraciones impacta en segundos.
- Si Configuraciones no responde, se usa la última copia hasta `configuraciones_copia_max_segundos`.
- Sin copia, **falla cerrado** (`ConfiguracionNoDisponible` → 503): el motor no puede fechar cuotas
  sin el calendario, ni el workflow decidir quién aprueba sin sus reglas. Nunca se inventa un valor.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)
MODULO = "creditos"
TIMEOUT = 5.0


class ConfiguracionNoDisponible(RuntimeError):
    """Configuraciones no respondió y no hay copia reciente: el llamador responde 503."""


class Fuente(Protocol):
    def get(self, path: str, params: dict | None = None) -> Any | None:
        """JSON de `GET /internal/configuraciones{path}`; None si es 404. Levanta ante cualquier otro error."""


class FuenteHttp:
    def get(self, path: str, params: dict | None = None) -> Any | None:
        s = get_settings()
        r = httpx.get(f"{s.configuraciones_service_url.rstrip('/')}/internal/configuraciones{path}",
                      params=params, headers={"X-Api-Key": s.configuraciones_internal_api_key}, timeout=TIMEOUT)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()


_fuente: Fuente = FuenteHttp()
_cache: dict[tuple, tuple[float, Any]] = {}


def usar_fuente(fuente: Fuente) -> None:
    """Cambia de dónde se lee la configuración (los tests usan una fuente en memoria)."""
    global _fuente
    _fuente = fuente
    limpiar_cache()


def limpiar_cache() -> None:
    _cache.clear()


def _leer(path: str, params: dict | None = None) -> Any | None:
    s = get_settings()
    clave = (path, tuple(sorted((params or {}).items())))
    ahora = time.monotonic()
    en_cache = _cache.get(clave)
    if en_cache and ahora - en_cache[0] < s.configuraciones_cache_segundos:
        return en_cache[1]
    try:
        valor = _fuente.get(path, params)
    except Exception as e:
        if en_cache and ahora - en_cache[0] < s.configuraciones_copia_max_segundos:
            log.warning("Configuraciones no responde (%s): se usa la copia de hace %.0fs", e, ahora - en_cache[0])
            return en_cache[1]
        raise ConfiguracionNoDisponible(f"El módulo Configuraciones no responde: {e}") from e
    _cache[clave] = (ahora, valor)
    return valor


# ── Catálogos ────────────────────────────────────────────────────────────────────────────────
def impuestos(estado: str = "activos") -> list[dict]:
    return (_leer("/impuestos", {"estado": estado}) or {}).get("items", [])


def indices(estado: str = "activos") -> list[dict]:
    return (_leer("/indices", {"estado": estado}) or {}).get("items", [])


def indice_valor(codigo: str | None) -> float | None:
    """Valor (% nominal anual) del índice, aunque esté dado de baja; None si no existe."""
    if not codigo:
        return None
    d = _leer(f"/indices/{codigo.upper()}")
    return float(d["valor"]) if d else None


def feriados(pais: str, desde: date, hasta: date) -> set[date]:
    d = _leer("/feriados", {"pais": pais.upper(), "desde": desde.isoformat(), "hasta": hasta.isoformat()}) or {}
    return {date.fromisoformat(f) for f in d.get("fechas", [])}


# ── Workflow ─────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class NivelWorkflow:
    orden: int
    nombre: str
    rol: str
    cuatro_ojos: bool
    incluidos: frozenset[str] = frozenset()   # aprueban aunque no tengan el rol
    excluidos: frozenset[str] = frozenset()   # no aprueban aunque lo tengan


@dataclass(frozen=True)
class ReglaWorkflow:
    objeto: str
    nombre: str
    activo: bool
    niveles: list[NivelWorkflow] = field(default_factory=list)


def regla_workflow(objeto: str) -> ReglaWorkflow | None:
    """Regla de aprobación de un objeto de Créditos (LINEA, SOLICITUD, DESEMBOLSO, REFINANCIACION)."""
    d = _leer(f"/workflow/{MODULO}/{objeto.upper()}")
    if not d:
        return None
    niveles = []
    for n in sorted(d.get("niveles", []), key=lambda x: x["orden"]):
        usuarios = n.get("usuarios", [])
        niveles.append(NivelWorkflow(
            orden=n["orden"], nombre=n.get("nombre", ""), rol=(n.get("rol") or "").upper(),
            cuatro_ojos=bool(n.get("cuatroOjos", True)),
            incluidos=frozenset(u["username"] for u in usuarios if u.get("modo") == "INCLUIR"),
            excluidos=frozenset(u["username"] for u in usuarios if u.get("modo") == "EXCLUIR")))
    return ReglaWorkflow(objeto=d["objeto"], nombre=d.get("nombre", ""), activo=bool(d.get("activo")),
                         niveles=niveles)
