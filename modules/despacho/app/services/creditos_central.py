"""Las solicitudes del anexo viven en Créditos, no acá.

Despacho emite el acto; las solicitudes son del módulo Créditos y él manda sobre ellas. Se consultan
y se asignan por su API interna, sin copiar la tabla de este lado: una solicitud en dos bases es una
solicitud que tarde o temprano dice dos cosas distintas.

Si Créditos no responde, la pantalla del anexo lo dice en vez de mostrar una lista vacía, que se
confundiría con "no hay nada para otorgar".
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import HTTPException

log = logging.getLogger("despacho.creditos")

URL = os.getenv("CREDITOS_SERVICE_URL", "http://creditos:8010").rstrip("/") + "/internal/creditos/anexo"
CLAVE = os.getenv("CREDITOS_INTERNAL_API_KEY", "")
TIMEOUT = float(os.getenv("CREDITOS_TIMEOUT", "20"))


def habilitado() -> bool:
    return bool(CLAVE)


def _pedir(metodo: str, ruta: str, **kw):
    if not habilitado():
        raise HTTPException(503, "El anexo necesita la conexión con Créditos, que no está configurada.")
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


def candidatas(*, linea_min: int | None = None, linea_max: int | None = None,
               cartera: int | None = None, lote: int | None = None) -> dict:
    params = {k: v for k, v in {"linea_min": linea_min, "linea_max": linea_max,
                                "cartera": cartera, "lote": lote}.items() if v is not None}
    return _pedir("GET", "/solicitudes", params=params)


def asignar(*, solicitud_ids: list[int], numero_resolucion: int, fecha_resolucion) -> dict:
    return _pedir("POST", "/asignar", json={
        "solicitud_ids": solicitud_ids, "numero_resolucion": numero_resolucion,
        "fecha_resolucion": fecha_resolucion.isoformat() if fecha_resolucion else None})


def quitar(solicitud_ids: list[int]) -> dict:
    return _pedir("POST", "/quitar", json={"solicitud_ids": solicitud_ids})
