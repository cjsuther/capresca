"""Cliente de la API interna de Tesorería: manda los pagos a agencias como un lote."""
import httpx

from app.config import settings


class TesoreriaNoDisponible(RuntimeError):
    pass


def enviar_lote(referencia: str, descripcion: str, pagos: list[dict]) -> dict:
    cuerpo = {"origen": "CONCILIACION", "referencia_origen": referencia, "descripcion": descripcion,
              "callback_url": settings.tesoreria_callback_url, "usuario": "conciliacion", "pagos": pagos}
    try:
        r = httpx.post(f"{settings.tesoreria_service_url.rstrip('/')}/internal/tesoreria/lotes", json=cuerpo,
                       headers={"X-Api-Key": settings.tesoreria_internal_api_key}, timeout=30.0)
    except httpx.HTTPError as e:
        raise TesoreriaNoDisponible(f"Tesorería no responde: {e}") from e
    if r.status_code == 422:
        detalle = r.json().get("detail")
        if isinstance(detalle, dict) and "rechazados" in detalle:
            return {"codigo": None, "pagos": [], "rechazados": detalle["rechazados"]}
    if r.status_code >= 400:
        raise TesoreriaNoDisponible(f"Tesorería rechazó el lote ({r.status_code}): {r.text[:200]}")
    return r.json()
