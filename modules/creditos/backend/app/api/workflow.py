"""Configuración del motor de workflow de aprobaciones (Seguridad → Workflow de aprobaciones)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.core.gateway import ROLES_APROBACION
from app.core.permisos import nivel_area
from app import models, models_productos as m
from app.services import workflow as wf

router = APIRouter(prefix="/api/creditos/workflow", tags=["workflow"])

# Roles que puede exigir un nivel: cada uno es un permiso de aprobación de Portezuelo (ver core/gateway.py).
PERFILES = list(ROLES_APROBACION)


def _puede_editar(user: models.Usuario) -> bool:
    return nivel_area(user, "seguridad") == "ESCRITURA"


def _req_admin(user: models.Usuario):
    if not _puede_editar(user):
        raise HTTPException(403, "Configurar el workflow exige el permiso de escritura de Seguridad (creditos:seguridad:write).")


def _rol_valido(rol: str) -> str:
    rol = (rol or "").upper()
    if rol not in ROLES_APROBACION:
        raise HTTPException(422, f"Rol inválido: {rol}. Opciones: {', '.join(ROLES_APROBACION)}.")
    return rol


def _serial_regla(r: m.PPWorkflowRegla) -> dict:
    return {
        "id": r.id, "objeto": r.objeto, "nombre": r.nombre, "descripcion": r.descripcion, "activo": r.activo,
        "niveles": [{
            "id": n.id, "orden": n.orden, "nombre": n.nombre, "rol": n.rol, "cuatroOjos": n.cuatro_ojos,
            "usuarios": [{"id": u.id, "username": u.username, "modo": u.modo} for u in n.usuarios],
        } for n in sorted(r.niveles, key=lambda x: x.orden)],
    }


@router.get("")
def listar(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    wf.seed_workflow(db)                                    # asegura las reglas por defecto
    reglas = db.query(m.PPWorkflowRegla).order_by(m.PPWorkflowRegla.creado_en).all()
    usuarios = [{"username": u.username, "perfil": (u.perfil or "").upper()}
                for u in db.query(models.Usuario).order_by(models.Usuario.username).all()]
    return {"reglas": [_serial_regla(r) for r in reglas], "perfiles": PERFILES, "usuarios": usuarios,
            "puedeEditar": _puede_editar(user)}


class ReglaIn(BaseModel):
    activo: bool | None = None
    nombre: str | None = None
    descripcion: str | None = None


@router.put("/{objeto}")
def editar_regla(objeto: str, data: ReglaIn, db: Session = Depends(get_db),
                 user: models.Usuario = Depends(get_current_user)):
    _req_admin(user)
    r = wf.regla(db, objeto)
    if not r:
        raise HTTPException(404, "Regla no encontrada")
    if data.activo is not None: r.activo = data.activo
    if data.nombre is not None: r.nombre = data.nombre
    if data.descripcion is not None: r.descripcion = data.descripcion
    db.commit()
    return _serial_regla(r)


class NivelIn(BaseModel):
    nombre: str = "Aprobación"
    rol: str = "APROBAR"
    cuatroOjos: bool = True


@router.post("/{objeto}/niveles", status_code=201)
def agregar_nivel(objeto: str, data: NivelIn, db: Session = Depends(get_db),
                  user: models.Usuario = Depends(get_current_user)):
    _req_admin(user)
    r = wf.regla(db, objeto)
    if not r:
        raise HTTPException(404, "Regla no encontrada")
    orden = (max([n.orden for n in r.niveles], default=0) + 1)
    db.add(m.PPWorkflowNivel(regla_id=r.id, orden=orden, nombre=data.nombre, rol=_rol_valido(data.rol),
                             cuatro_ojos=data.cuatroOjos))
    db.commit()
    return _serial_regla(r)


@router.put("/niveles/{nivel_id}")
def editar_nivel(nivel_id: str, data: NivelIn, db: Session = Depends(get_db),
                 user: models.Usuario = Depends(get_current_user)):
    _req_admin(user)
    n = db.get(m.PPWorkflowNivel, nivel_id)
    if not n:
        raise HTTPException(404, "Nivel no encontrado")
    n.nombre = data.nombre; n.rol = _rol_valido(data.rol); n.cuatro_ojos = data.cuatroOjos
    db.commit()
    return _serial_regla(n.regla)


@router.delete("/niveles/{nivel_id}")
def borrar_nivel(nivel_id: str, db: Session = Depends(get_db),
                 user: models.Usuario = Depends(get_current_user)):
    _req_admin(user)
    n = db.get(m.PPWorkflowNivel, nivel_id)
    if not n:
        raise HTTPException(404, "Nivel no encontrado")
    r = n.regla
    if len(r.niveles) <= 1:
        raise HTTPException(409, "La regla debe tener al menos un nivel de aprobación.")
    db.delete(n)
    # recompactar el orden 1..N
    for i, x in enumerate(sorted([x for x in r.niveles if x.id != n.id], key=lambda z: z.orden), start=1):
        x.orden = i
    db.commit()
    return _serial_regla(r)


class OverrideIn(BaseModel):
    username: str
    modo: str = "INCLUIR"   # INCLUIR | EXCLUIR


@router.post("/niveles/{nivel_id}/usuarios", status_code=201)
def agregar_override(nivel_id: str, data: OverrideIn, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(get_current_user)):
    _req_admin(user)
    n = db.get(m.PPWorkflowNivel, nivel_id)
    if not n:
        raise HTTPException(404, "Nivel no encontrado")
    if data.modo not in ("INCLUIR", "EXCLUIR"):
        raise HTTPException(422, "Modo inválido (INCLUIR | EXCLUIR).")
    if not db.query(models.Usuario).filter_by(username=data.username).first():
        raise HTTPException(404, "Usuario inexistente.")
    ya = next((u for u in n.usuarios if u.username == data.username), None)
    if ya:
        ya.modo = data.modo
    else:
        db.add(m.PPWorkflowNivelUsuario(nivel_id=n.id, username=data.username, modo=data.modo))
    db.commit()
    return _serial_regla(n.regla)


@router.delete("/usuarios/{override_id}")
def borrar_override(override_id: str, db: Session = Depends(get_db),
                    user: models.Usuario = Depends(get_current_user)):
    _req_admin(user)
    o = db.get(m.PPWorkflowNivelUsuario, override_id)
    if not o:
        raise HTTPException(404, "Override no encontrado")
    r = o.nivel.regla
    db.delete(o); db.commit()
    return _serial_regla(r)
