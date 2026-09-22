"""Dependencias comunes de FastAPI: sesión de usuario y control de acceso.

El usuario del backoffice lo autentica el gateway de Portezuelo (ver `app/core/gateway.py`). Acá sólo se
lee su identidad de los headers y se vincula con el `Usuario` local por username; el `Usuario` local se
crea en el primer acceso y existe para auditoría, workflow y trazabilidad (aprobado_por, emisor...).
"""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from jwt import InvalidTokenError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.gateway import identidad
from app.core.security import decode_token
from app import models

# Perfil con el que se crea el Usuario local de un usuario de Portezuelo (el perfil ya no autoriza nada).
PERFIL_SSO = "SSO"


@dataclass
class Actor:
    """Quién y desde dónde origina una mutación, para auditoría.

    Autenticación OPCIONAL: no lanza 401 si no hay identidad (a diferencia de
    get_current_user). Un endpoint sin sesión igual queda auditado como 'anonimo'.
    """
    usuario: str = "anonimo"
    perfil: str = ""
    ip: str = ""


def get_actor(request: Request) -> Actor:
    from app.services.auditoria import ip_de
    actor = Actor(ip=ip_de(request))
    ident = identidad(request)
    if ident:
        actor.usuario, actor.perfil = ident.username, PERFIL_SSO
    return actor


def _usuario_local(db: Session, username: str) -> models.Usuario:
    """Usuario local vinculado por username; se crea en el primer acceso. La unique de `username` es el
    árbitro si dos requests concurrentes lo crean a la vez: el perdedor relee el que quedó."""
    u = db.query(models.Usuario).filter_by(username=username).first()
    if u:
        return u
    try:
        u = models.Usuario(username=username, nombre=username, password_hash="!", perfil=PERFIL_SSO, activo=True)
        db.add(u)
        db.commit()
    except IntegrityError:
        db.rollback()
        u = db.query(models.Usuario).filter_by(username=username).one()
    return u


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    ident = identidad(request)
    if ident is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión requerida: ingresá desde Portezuelo.")
    if len(ident.username) > 30:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "El módulo Créditos admite usernames de hasta 30 caracteres.")
    user = _usuario_local(db, ident.username)
    # Atributo transitorio (no mapeado): lo leen app/core/permisos.py y el workflow.
    user.permisos_gateway = ident.permisos
    return user


@dataclass
class Ciudadano:
    """Identidad del portal (autenticada por Mi Catamarca). NO es un Usuario del backoffice."""
    sub: str
    email: str = ""
    nombre: str = ""
    documento: str = ""


def get_ciudadano(request: Request) -> Ciudadano:
    """Auth del PORTAL: exige un token con scope 'portal' firmado por este módulo."""
    cred_exc = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión de portal inválida",
                             headers={"WWW-Authenticate": "Bearer"})
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise cred_exc
    try:
        payload = decode_token(auth[7:])
    except InvalidTokenError:
        raise cred_exc
    if payload.get("scope") != "portal":
        raise cred_exc
    return Ciudadano(sub=payload.get("sub", ""), email=payload.get("email", ""),
                     nombre=payload.get("nombre", ""), documento=payload.get("documento", ""))


def requiere_perfil(*prefijos: str):
    """Compatibilidad con los endpoints que restringían por perfil VFP (symdeperf).

    El acceso por área lo decide ahora el gateway según el prefijo de la ruta (`caja:read`,
    `tesoreria:write`...), así que acá sólo se exige un usuario autenticado. Los prefijos quedan en las
    firmas como documentación del perfil original.
    """
    def checker(user: models.Usuario = Depends(get_current_user)) -> models.Usuario:
        return user
    return checker
