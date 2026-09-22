"""Identidad que inyecta el gateway y clave de la API interna.

El gateway valida el JWT, resuelve los permisos del usuario y los manda en `X-User-*`; además ya
exige el permiso de cada ruta (`proxy/app/routes/mapping.py`). Acá se revalida el permiso de
escritura (defensa en profundidad): una request que llegue sin pasar por el gateway no escribe.
"""
from fastapi import Depends, Header, HTTPException

from app.config import settings

MODULO = "contabilidad"


class Usuario:
    def __init__(self, user_id: int, username: str, permisos: frozenset[str]):
        self.user_id, self.username, self.permisos = user_id, username, permisos

    def puede(self, accion: str) -> bool:
        return f"{MODULO}:{accion}" in self.permisos


def usuario_actual(x_user_id: str = Header(""), x_username: str = Header(""),
                   x_user_permissions: str = Header("")) -> Usuario:
    if not x_user_id.isdigit():
        raise HTTPException(401, "Falta la identidad del gateway (X-User-Id).")
    permisos = frozenset(p.strip() for p in x_user_permissions.split(",") if p.strip())
    return Usuario(int(x_user_id), x_username or f"usuario-{x_user_id}", permisos)


def requiere(accion: str):
    """Dependencia: exige `contabilidad:<accion>` (p.ej. `asientos:write`)."""
    def dep(user: Usuario = Depends(usuario_actual)) -> Usuario:
        if not user.puede(accion):
            raise HTTPException(403, f"Falta el permiso {MODULO}:{accion} (Seguridad).")
        return user
    return dep


def api_interna(x_api_key: str = Header("")) -> None:
    """La API interna sólo la usan otros módulos, con la clave compartida. Sin clave configurada,
    queda cerrada (no abierta por defecto)."""
    if not settings.internal_api_key or x_api_key != settings.internal_api_key:
        raise HTTPException(401, "API interna: clave inválida.")
