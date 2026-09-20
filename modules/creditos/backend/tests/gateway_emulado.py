"""Emulación del gateway de Portezuelo para los tests.

En producción el módulo no autentica: el proxy valida el JWT del sistema y reenvía la request con
X-User-Id / X-Username / X-User-Permissions (ver app/core/gateway.py). Los tests siguen usando los
usuarios sembrados por perfil (admin/ADMG, creditos/XCR, ...), así que acá se reproduce lo que haría un
administrador en Seguridad de Portezuelo:

- `POST /api/creditos/auth/login` (sólo en tests) valida el usuario sembrado y emite un token de prueba.
- Un middleware ASGI traduce ese Bearer en los headers del gateway, con los permisos por área derivados
  de los roles del usuario (perfil + roles directos + grupos vigentes):
    ADMG → todas las áreas en escritura + aprobar + supervisar
    SUPE → aprobar + supervisar;  XCR / OPER / SUPE → creditos:write
    resto de las áreas → escritura, salvo que sus roles tengan permisos por pantalla cargados
    (PerfilPermiso / UsuarioPermiso): entonces el nivel del área es el máximo de sus pantallas.
"""
from datetime import date

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models
from app.core import security
from app.core.database import SessionLocal, get_db
from app.core.gateway import AREAS, MODULO, PERMISO_APROBAR, PERMISO_SUPERVISAR
from app.core.permisos import area_de_ruta
from app.main import app

_SECRETO = "test-gateway"
_EDITA = {"ADMG", "XCR", "OPER", "SUPE"}
_APRUEBA = {"ADMG", "SUPE"}
_ORDEN = {"NINGUNO": 0, "CONSULTA": 1, "ESCRITURA": 2, "TOTAL": 3}

router = APIRouter(prefix="/api/creditos/auth", tags=["auth-test"])


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.Usuario).filter_by(username=form.username, activo=True).first()
    if not user or not security.verify_password(form.password, user.password_hash):
        raise HTTPException(401, "Usuario o contraseña inválidos")
    pf = db.query(models.Perfil).filter_by(codigo=(user.perfil or "").upper()).first()
    if pf is not None and not pf.habilitado:
        raise HTTPException(403, "Tu perfil está deshabilitado.")
    token = jwt.encode({"sub": user.username, "scope": "test-gateway"}, _SECRETO, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "perfil": user.perfil, "nombre": user.nombre}


def _vig(desde, hasta, hoy):
    return (desde is None or desde <= hoy) and (hasta is None or hoy <= hasta)


def _roles(db: Session, user: models.Usuario, hoy: date) -> set[str]:
    roles = {(user.perfil or "").upper()}
    for ur in db.query(models.UsuarioPerfil).filter_by(usuario_id=user.id).all():
        if _vig(ur.vigente_desde, ur.vigente_hasta, hoy):
            roles.add((ur.perfil_codigo or "").upper())
    grupos = [ug.grupo_codigo for ug in db.query(models.UsuarioGrupo).filter_by(usuario_id=user.id).all()
              if _vig(ug.vigente_desde, ug.vigente_hasta, hoy)]
    if grupos:
        activos = {c for (c,) in db.query(models.Grupo.codigo).filter(
            models.Grupo.codigo.in_(grupos), models.Grupo.activo.is_(True)).all()}
        for gr in db.query(models.GrupoRol).filter(models.GrupoRol.grupo_codigo.in_(activos)).all():
            roles.add((gr.rol_codigo or "").upper())
    return {r for r in roles if r}


def permisos_de(db: Session, user: models.Usuario) -> set[str]:
    hoy = date.today()
    roles = _roles(db, user, hoy)
    if "ADMG" in roles:
        perms = {f"{a}:write" for a in AREAS} | {f"{a}:read" for a in AREAS}
        return perms | {PERMISO_APROBAR, PERMISO_SUPERVISAR}
    filas = [(f.ruta, f.nivel) for f in db.query(models.PerfilPermiso).filter(
        models.PerfilPermiso.perfil_codigo.in_(roles)).all()]
    filas += [(u.ruta, u.nivel) for u in db.query(models.UsuarioPermiso).filter_by(usuario_id=user.id).all()
              if _vig(u.vigente_desde, u.vigente_hasta, hoy)]
    if filas:
        nivel: dict[str, str] = {}
        for ruta, n in filas:
            a = area_de_ruta(ruta)
            if a and _ORDEN[n] > _ORDEN[nivel.get(a, "NINGUNO")]:
                nivel[a] = n
    else:
        nivel = {a: "ESCRITURA" for a in AREAS}
    nivel["creditos"] = "ESCRITURA" if roles & _EDITA else ("CONSULTA" if _ORDEN[nivel.get("creditos", "NINGUNO")] else "NINGUNO")
    perms: set[str] = set()
    for a, n in nivel.items():
        if _ORDEN[n] >= 1:
            perms.add(f"{a}:read")
        if _ORDEN[n] >= 2:
            perms.add(f"{a}:write")
    if roles & _APRUEBA:
        perms |= {PERMISO_APROBAR, PERMISO_SUPERVISAR}
    return perms


class GatewayEmulado:
    """ASGI: Bearer de prueba → headers X-User-* (como routes/proxy.py del gateway)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Sólo actúa ante un Bearer de prueba; los tests que mandan X-User-* directo simulan la salida
        # del gateway y pasan tal cual.
        if scope["type"] == "http":
            auth = dict(scope["headers"]).get(b"authorization", b"").decode()
            payload = {}
            if auth.lower().startswith("bearer "):
                try:
                    payload = jwt.decode(auth[7:], _SECRETO, algorithms=["HS256"])
                except jwt.InvalidTokenError:
                    pass
            if payload.get("scope") == "test-gateway":
                headers = [(k, v) for k, v in scope["headers"] if not k.lower().startswith(b"x-user-")]
                with SessionLocal() as db:
                    user = db.query(models.Usuario).filter_by(username=payload["sub"], activo=True).first()
                    if user:
                        perms = ",".join(sorted(f"{MODULO}:{p}" for p in permisos_de(db, user)))
                        headers += [(b"x-user-id", str(user.id).encode()), (b"x-username", user.username.encode()),
                                    (b"x-user-permissions", perms.encode())]
                scope = dict(scope, headers=headers)
        await self.app(scope, receive, send)


app.include_router(router)
app.add_middleware(GatewayEmulado)
