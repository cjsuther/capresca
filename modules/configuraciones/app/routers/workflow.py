"""Definición del workflow de aprobaciones (cuatro-ojos / N-ojos en serie) de cada módulo.

Configurarlo exige `configuraciones:workflow:write`, un permiso aparte del de operar el módulo:
quien diseña o carga créditos no puede sacarse de encima su propio control."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere, usuario_actual
from app.services.workflow import ROLES, sembrar_reglas, serial_regla

router = APIRouter(prefix="/workflow", tags=["workflow"])
_escribe = requiere("workflow:write")


class ReglaIn(BaseModel):
    activo: bool | None = None
    nombre: str | None = Field(None, max_length=80)
    descripcion: str | None = Field(None, max_length=200)


class NivelIn(BaseModel):
    nombre: str = Field("Aprobación", min_length=1, max_length=60)
    rol: str = "APROBAR"
    cuatroOjos: bool = True


class OverrideIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    modo: str = "INCLUIR"


def _rol(rol: str) -> str:
    rol = (rol or "").upper()
    if rol not in ROLES:
        raise HTTPException(422, f"Rol inválido: {rol}. Opciones: {', '.join(ROLES)}.")
    return rol


def _regla(db: Session, regla_id: int) -> models.WorkflowRegla:
    r = db.get(models.WorkflowRegla, regla_id)
    if not r:
        raise HTTPException(404, "Regla no encontrada")
    return r


def _nivel(db: Session, nivel_id: int) -> models.WorkflowNivel:
    n = db.get(models.WorkflowNivel, nivel_id)
    if not n:
        raise HTTPException(404, "Nivel no encontrado")
    return n


@router.get("")
def listar(modulo: str | None = Query(None), db: Session = Depends(get_db),
           user: Usuario = Depends(usuario_actual)):
    sembrar_reglas(db)   # un módulo nuevo en el catálogo aparece sin esperar al próximo arranque
    q = db.query(models.WorkflowRegla)
    if modulo:
        q = q.filter(models.WorkflowRegla.modulo == modulo)
    reglas = q.order_by(models.WorkflowRegla.modulo, models.WorkflowRegla.id).all()
    return {"reglas": [serial_regla(r) for r in reglas], "roles": list(ROLES),
            "puedeEditar": user.puede("workflow:write")}


@router.put("/reglas/{regla_id}")
def editar_regla(regla_id: int, data: ReglaIn, db: Session = Depends(get_db), _=Depends(_escribe)):
    r = _regla(db, regla_id)
    if data.activo is not None:
        r.activo = data.activo
    if data.nombre is not None:
        r.nombre = data.nombre.strip()
    if data.descripcion is not None:
        r.descripcion = data.descripcion.strip()
    db.commit()
    return serial_regla(r)


@router.post("/reglas/{regla_id}/niveles", status_code=201)
def agregar_nivel(regla_id: int, data: NivelIn, db: Session = Depends(get_db), _=Depends(_escribe)):
    r = _regla(db, regla_id)
    orden = max((n.orden for n in r.niveles), default=0) + 1
    r.niveles.append(models.WorkflowNivel(orden=orden, nombre=data.nombre.strip(), rol=_rol(data.rol),
                                          cuatro_ojos=data.cuatroOjos))
    db.commit()
    return serial_regla(r)


@router.put("/niveles/{nivel_id}")
def editar_nivel(nivel_id: int, data: NivelIn, db: Session = Depends(get_db), _=Depends(_escribe)):
    n = _nivel(db, nivel_id)
    n.nombre, n.rol, n.cuatro_ojos = data.nombre.strip(), _rol(data.rol), data.cuatroOjos
    db.commit()
    return serial_regla(n.regla)


@router.delete("/niveles/{nivel_id}")
def borrar_nivel(nivel_id: int, db: Session = Depends(get_db), _=Depends(_escribe)):
    n = _nivel(db, nivel_id)
    r = n.regla
    if len(r.niveles) <= 1:
        raise HTTPException(409, "La regla debe tener al menos un nivel de aprobación.")
    r.niveles.remove(n)
    for i, x in enumerate(sorted(r.niveles, key=lambda z: z.orden), start=1):   # recompacta 1..N
        x.orden = i
    db.commit()
    return serial_regla(r)


@router.post("/niveles/{nivel_id}/usuarios", status_code=201)
def agregar_override(nivel_id: int, data: OverrideIn, db: Session = Depends(get_db), _=Depends(_escribe)):
    n = _nivel(db, nivel_id)
    if data.modo not in ("INCLUIR", "EXCLUIR"):
        raise HTTPException(422, "Modo inválido (INCLUIR | EXCLUIR).")
    username = data.username.strip()
    ya = next((u for u in n.usuarios if u.username == username), None)
    if ya:
        ya.modo = data.modo
    else:
        n.usuarios.append(models.WorkflowNivelUsuario(username=username, modo=data.modo))
    db.commit()
    return serial_regla(n.regla)


@router.delete("/usuarios/{override_id}")
def borrar_override(override_id: int, db: Session = Depends(get_db), _=Depends(_escribe)):
    o = db.get(models.WorkflowNivelUsuario, override_id)
    if not o:
        raise HTTPException(404, "Override no encontrado")
    regla = o.nivel.regla
    o.nivel.usuarios.remove(o)
    db.commit()
    return serial_regla(regla)
