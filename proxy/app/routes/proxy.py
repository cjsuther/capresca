"""
Router catch-all: reenvía todas las solicitudes /api/* al microservicio correspondiente.
"""
import logging

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.routes.mapping import get_service_url

logger = logging.getLogger("proxy.router")

router = APIRouter()


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

    # Copiar headers (excluir host)
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    # Inyectar usuario autenticado
    if hasattr(request.state, "user_id"):
        headers["X-User-Id"] = str(request.state.user_id)
        headers["X-Username"] = request.state.username

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
            )

        logger.info("%s %s → %s [%d]", request.method, full_path, target_url, resp.status_code)

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type"),
        )

    except httpx.RequestError as exc:
        logger.error("Error al reenviar solicitud a %s: %s", target_url, exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "Servicio no disponible", "service": service_url},
        )
