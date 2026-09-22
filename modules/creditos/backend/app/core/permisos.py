"""Autorización del módulo a partir de los permisos por ÁREA que resuelve Portezuelo.

Los permisos se administran en Seguridad de Portezuelo (módulo `creditos`) y llegan con cada request en los
headers del gateway (ver `app/core/gateway.py`). El gateway ya exige el permiso del área según el prefijo de
la API; este módulo los usa para:

- las dependencias `requiere_permiso` (defensa en profundidad sobre rutas puntuales),
- las capacidades del circuito de créditos (editar / aprobar) y los roles del workflow de aprobaciones.

Niveles: NINGUNO < CONSULTA (`<area>:read`) < ESCRITURA (`<area>:write`).
"""
from datetime import date

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.core.database import get_db
from app.core.gateway import AREAS, ROLES_APROBACION
from app.deps import get_current_user

ORDEN = {"NINGUNO": 0, "CONSULTA": 1, "ESCRITURA": 2, "TOTAL": 3}

def permisos_de(user: models.Usuario) -> frozenset[str]:
    """Acciones del módulo que tiene el usuario (sin prefijo `creditos:`). Vacío si no vino del gateway."""
    return getattr(user, "permisos_gateway", frozenset())


def area_de_ruta(ruta: str) -> str | None:
    """Área de una ruta del front (`/caja/cobranza` → `caja`)."""
    seg = ruta.strip("/").split("/", 1)[0]
    return seg if seg in AREAS else None


def nivel_area(user: models.Usuario, area: str) -> str:
    perms = permisos_de(user)
    if f"{area}:write" in perms:
        return "ESCRITURA"
    if f"{area}:read" in perms:
        return "CONSULTA"
    return "NINGUNO"


def roles_de(db: Session, user: models.Usuario, hoy: date | None = None) -> set[str]:
    """Roles de aprobación del usuario (los que puede exigir un nivel del workflow)."""
    perms = permisos_de(user)
    return {rol for rol, permiso in ROLES_APROBACION.items() if permiso in perms}


# Alias de compatibilidad (código previo llamaba perfiles_de).
def perfiles_de(db: Session, user: models.Usuario) -> set[str]:
    return roles_de(db, user)


def sin_restricciones(db: Session, user: models.Usuario) -> bool:
    """Con permisos administrados en Portezuelo no hay usuarios "sin RBAC configurado"."""
    return False


def nivel_efectivo(db: Session, user: models.Usuario, ruta: str) -> str:
    area = area_de_ruta(ruta)
    return nivel_area(user, area) if area else "NINGUNO"


def permisos_efectivos(db: Session, user: models.Usuario) -> dict[str, str]:
    """{ área: nivel } de las áreas a las que el usuario tiene acceso."""
    niveles = {area: nivel_area(user, area) for area in AREAS}
    return {a: n for a, n in niveles.items() if n != "NINGUNO"}


# ---- Capacidades del circuito de créditos ----
def caps_creditos(db: Session, user: models.Usuario) -> dict:
    """{edita, aprueba}: diseñar/editar/enviar a revisión exige `creditos:write`; aprobar/publicar exige
    algún permiso de aprobación (el cuatro-ojos lo cierra el workflow)."""
    return {"edita": nivel_area(user, "creditos") == "ESCRITURA",
            "aprueba": bool(roles_de(db, user))}


def requiere_permiso(ruta: str, minimo: str = "CONSULTA"):
    """Dependencia FastAPI: exige que el usuario tenga al menos `minimo` sobre el área de la pantalla `ruta`."""
    def dep(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
        if ORDEN[nivel_efectivo(db, user, ruta)] < ORDEN[minimo]:
            raise HTTPException(403, f"Tu usuario no tiene permiso de {minimo.lower()} sobre esta pantalla.")
        return user
    return dep
