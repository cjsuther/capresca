"""Fuente de haberes del ciudadano (sueldo neto + antigüedad + relación laboral).

Idea #2 del memo de migración: en vez de que el ciudadano declare sus haberes, traerlos de una
fuente oficial (Mi Catamarca / RRHH provincial). Ese scope/API TODAVÍA NO EXISTE, así que esto queda
detrás de una interfaz desacoplada:
  - proveedor REAL: pega al `haberes_api_url` con token (cuando exista), keyed por documento;
  - proveedor MOCK: datos demo deterministas (dev/demo/tests) — el ciudadano igual puede declarar.

Para enchufar el API real: setear HABERES_API_URL/HABERES_API_TOKEN por entorno e implementar el
parseo de la respuesta en `HaberesRealProvider.por_documento`.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class Haberes:
    disponible: bool = False           # False = la fuente no pudo resolver los haberes
    sueldo: float | None = None        # neto mensual
    antiguedad_meses: int | None = None
    segmento: str = ""                 # relación laboral (AGENTE_PUBLICO, DOCENTE…)
    empleador: str = ""
    fuente: str = ""                   # "micatamarca" | "mock" | ""


class HaberesRealProvider:
    """Consulta el API oficial de haberes por documento (cuando exista)."""
    mock = False

    def __init__(self, s):
        self.s = s

    def por_documento(self, documento: str, sub: str = "") -> Haberes:
        try:
            with httpx.Client(timeout=10) as c:
                r = c.get(self.s.haberes_api_url, params={"documento": documento},
                          headers={"Authorization": f"Bearer {self.s.haberes_api_token}"})
                r.raise_for_status()
                d = r.json()
            # Mapeo tolerante a nombres alternativos (ajustar al contrato real cuando se conozca).
            return Haberes(
                disponible=True,
                sueldo=_num(d.get("sueldo_neto") or d.get("sueldoNeto") or d.get("sueldo")),
                antiguedad_meses=_int(d.get("antiguedad_meses") or d.get("antiguedadMeses")),
                segmento=(d.get("segmento") or d.get("relacion") or "").upper(),
                empleador=d.get("empleador") or d.get("organismo") or "",
                fuente="micatamarca")
        except Exception:
            return Haberes(disponible=False)


class MockHaberes:
    """Datos demo deterministas (sin red). El ciudadano igual puede editar lo que trae."""
    mock = True

    def por_documento(self, documento: str, sub: str = "") -> Haberes:
        return Haberes(disponible=True, sueldo=920000.0, antiguedad_meses=96, segmento="AGENTE_PUBLICO",
                       empleador="Gobierno de la Provincia de Catamarca (demo)", fuente="mock")


def _num(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def get_provider():
    """Proveedor real si hay API configurada; si no, el mock (dev/demo/tests)."""
    s = get_settings()
    return HaberesRealProvider(s) if s.haberes_configurado else MockHaberes()
