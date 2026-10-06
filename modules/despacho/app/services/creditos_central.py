"""Los lotes de solicitudes viven en Créditos, no acá.

Despacho emite el acto; los lotes y sus solicitudes son del módulo Créditos y él manda sobre ellos.
Se consultan y se les asigna la resolución por su API interna, sin copiar la tabla de este lado: un
lote en dos bases es un lote que tarde o temprano dice dos cosas distintas.

Si Créditos no responde, la pantalla lo dice en vez de mostrar una lista vacía, que se confundiría
con "no hay nada para otorgar".
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import HTTPException

log = logging.getLogger("despacho.creditos")

URL = os.getenv("CREDITOS_SERVICE_URL", "http://creditos:8010").rstrip("/") + "/internal/creditos/lotes"
CLAVE = os.getenv("CREDITOS_INTERNAL_API_KEY", "")
TIMEOUT = float(os.getenv("CREDITOS_TIMEOUT", "20"))


def habilitado() -> bool:
    return bool(CLAVE)


def _pedir(metodo: str, ruta: str, **kw):
    if not habilitado():
        raise HTTPException(503, "Los lotes necesitan la conexión con Créditos, que no está configurada.")
    try:
        with httpx.Client(timeout=TIMEOUT) as c:
            r = c.request(metodo, f"{URL}{ruta}", headers={"X-Api-Key": CLAVE}, **kw)
    except httpx.HTTPError as e:                          # Créditos caído o inalcanzable
        log.warning("Créditos no responde (%s %s): %s", metodo, ruta, e)
        raise HTTPException(503, "Créditos no responde; probá de nuevo en un momento.") from e
    if r.status_code >= 400:
        # El motivo que da Créditos es el que tiene que ver el operador (p. ej. "ya están en otra
        # resolución"), no un error genérico de integración.
        detalle = ""
        try:
            detalle = (r.json() or {}).get("detail", "")
        except ValueError:
            pass
        raise HTTPException(r.status_code if r.status_code < 500 else 502,
                            detalle or f"Créditos respondió {r.status_code}.")
    return r.json()


def tipos() -> list[dict]:
    """Los tipos de crédito por los que se arman los lotes: los productos."""
    return _pedir("GET", "/tipos")


def lotes(*, estado: str | None = None, producto_id: str | None = None, resolucion_id: int | None = None,
          numero: int = 0, anio: int | None = None) -> dict:
    params = {k: v for k, v in {"estado": estado, "producto_id": producto_id, "resolucion_id": resolucion_id,
                                "numero": numero, "anio": anio}.items() if v}
    return _pedir("GET", "", params=params)


def lote(lote_id: int) -> dict:
    return _pedir("GET", f"/{lote_id}")


def asignar_resolucion(lote_ids: list[int], resolucion: dict) -> dict:
    return _pedir("POST", "/asignar-resolucion", json={"lote_ids": lote_ids, "resolucion": resolucion})


def quitar_resolucion(lote_id: int) -> dict:
    return _pedir("POST", f"/{lote_id}/quitar-resolucion")


def resolucion_actualizada(resolucion: dict) -> dict:
    return _pedir("POST", "/resolucion", json=resolucion)


def solicitudes_de_resolucion(resolucion_id: int, numero: int, anio: int) -> dict:
    return _pedir("GET", "/resolucion/solicitudes",
                  params={"resolucion_id": resolucion_id, "numero": numero, "anio": anio})
