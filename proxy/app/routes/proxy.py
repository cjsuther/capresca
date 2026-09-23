"""
Router catch-all: reenvía todas las solicitudes /api/* al microservicio correspondiente.
"""
import json
import logging
import uuid

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes.mapping import get_service_url
from app.services import auditoria

logger = logging.getLogger("proxy.router")

router = APIRouter()

# Lo que cambia información del sistema: se audita siempre (las lecturas, no: serían ruido).
MUTANTES = ("POST", "PUT", "PATCH", "DELETE")


def _ip(request: Request) -> str:
    fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return (fwd or (request.client.host if request.client else ""))[:64]


def _usuario_del_login(body: bytes) -> str:
    """Un login todavía no tiene identidad: se toma el usuario que intenta entrar (nunca la clave)."""
    try:
        return str(json.loads(body or b"{}").get("username") or "")[:60]
    except Exception:
        return ""


def _auditar(request: Request, full_path: str, body: bytes, status: int, request_id: str) -> None:
    """Deja el evento en la cola de Auditoría. No puede fallar hacia afuera."""
    if request.method not in MUTANTES:
        return
    partes = full_path.strip("/").split("/")          # api/<modulo>/...
    modulo = partes[1] if len(partes) > 1 else ""
    es_login = full_path.startswith("/api/auth/")
    if es_login:
        modulo = "security"
    usuario = getattr(request.state, "username", "") or (_usuario_del_login(body) if es_login else "")
    auditoria.registrar({
        "usuario": usuario, "usuario_id": getattr(request.state, "user_id", None), "ip": _ip(request),
        "modulo": modulo, "operacion": "ACCESO" if es_login else None,
        "metodo": request.method, "ruta": full_path, "estado_http": status,
        "origen": "GATEWAY", "request_id": request_id,
    })


@router.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_request(path: str, request: Request):
    full_path = f"/api/{path}"
    service_url = get_service_url(request.method, full_path)

    if service_url is None:
        return JSONResponse(status_code=404, content={"detail": f"Ruta no encontrada: {full_path}"})

    # Construir URL destino
    target_url = f"{service_url}{full_path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Copiar headers, descartando los de identidad/autorización que pueda mandar el cliente: sólo los
    # inyecta el gateway. Las claves llegan en minúscula y las nuestras no: si no se descartan, httpx
    # manda AMBAS y el módulo lee la primera (la del cliente) → suplantación.
    # `x-permissions` y `x-api-key` también se descartan: los módulos los usan para decidir acceso.
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length", "x-permissions", "x-api-key")
        and not k.lower().startswith("x-user")
    }
    # Inyectar usuario autenticado y sus permisos efectivos ("modulo:accion" separados por coma)
    if hasattr(request.state, "user_id"):
        headers["X-User-Id"] = str(request.state.user_id)
        headers["X-Username"] = request.state.username
        actions = request.state.permissions.get("actions", {})
        headers["X-User-Permissions"] = ",".join(
            f"{module}:{action}" for module, codes in sorted(actions.items()) for action in sorted(codes)
        )

    body = await request.body()
    # Identificador de la operación: viaja al módulo para que su detalle (qué registro tocó y qué
    # cambió) se pueda cruzar con lo que registra el gateway.
    request_id = uuid.uuid4().hex[:32]
    headers["X-Request-Id"] = request_id

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(settings.upstream_timeout, connect=10.0)) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

        logger.info("%s %s → %s [%d]", request.method, full_path, target_url, resp.status_code)
        _auditar(request, full_path, body, resp.status_code, request_id)

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type"),
        )

    except httpx.RequestError as exc:
        logger.error("Error al reenviar solicitud a %s: %s", target_url, exc)
        _auditar(request, full_path, body, 502, request_id)
        return JSONResponse(
            status_code=502,
            content={"detail": "Servicio no disponible", "service": service_url},
        )
