"""Identidad y permisos que inyecta el gateway de Portezuelo.

Créditos no autentica usuarios del backoffice: el proxy (`proxy/`) valida el JWT del sistema, resuelve
los permisos del usuario contra el módulo security y reenvía la request con estos headers:

- `X-User-Id`           id del usuario en security
- `X-Username`          username (clave con la que se vincula el `Usuario` local)
- `X-User-Permissions`  permisos efectivos, `modulo:accion` separados por coma

El proxy descarta cualquier `X-User-*` que mande el cliente, y nginx sólo publica el módulo a través del
proxy (salvo `/api/creditos/portal/`, que usa el realm propio del ciudadano y nunca lee estos headers).

Los permisos del módulo se modelan POR ÁREA (`<area>:read` / `<area>:write`) más dos de aprobación
para el workflow cuatro-ojos/N-ojos. El catálogo tiene que coincidir con `modules/security/app/seed.py`
y con el mapeo de rutas de `proxy/app/routes/mapping.py`.
"""
from dataclasses import dataclass

from fastapi import Request

MODULO = "creditos"

# código de área → etiqueta. Cada área es un par de permisos `<area>:read` / `<area>:write`.
AREAS: dict[str, str] = {
    "clientes": "Clientes",
    "creditos": "Créditos",
    "caja": "Caja",
    "tesoreria": "Tesorería",
    "contabilidad": "Contabilidad",
    "seguros": "Seguros",
    "despacho": "Despacho",
    "mesa": "Mesa de entradas",
    "juegos": "Juegos / Quiniela",
    "general": "General (tablas maestras)",
    "seguridad": "Seguridad (auditoría, workflow, controles)",
}

# Permisos de aprobación: cada nivel del workflow exige uno de estos "roles" (ver services/workflow.py).
PERMISO_APROBAR = "aprobaciones:aprobar"
PERMISO_SUPERVISAR = "aprobaciones:supervisar"
ROLES_APROBACION = {"APROBAR": PERMISO_APROBAR, "SUPERVISAR": PERMISO_SUPERVISAR}


@dataclass(frozen=True)
class Identidad:
    user_id: int
    username: str
    permisos: frozenset[str]   # acciones de ESTE módulo, sin el prefijo `creditos:` (p.ej. "caja:write")


def identidad(request: Request) -> Identidad | None:
    """Identidad del usuario según los headers del gateway, o None si la request no la trae."""
    uid = request.headers.get("x-user-id", "")
    username = request.headers.get("x-username", "")
    if not uid.isdigit() or not username:
        return None
    prefijo = MODULO + ":"
    permisos = frozenset(
        p[len(prefijo):] for p in (x.strip() for x in request.headers.get("x-user-permissions", "").split(","))
        if p.startswith(prefijo)
    )
    return Identidad(user_id=int(uid), username=username, permisos=permisos)
