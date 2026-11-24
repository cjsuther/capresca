"""API del workflow gráfico versionado (procesos, versiones, borrador, publicación).

Permisos (el gateway los exige antes; acá se revalidan):
  - `workflow:read`    ver procesos, versiones y comparar;
  - `workflow:write`   crear, guardar (autosave) y descartar BORRADORES. No pide step-up: un borrador
                       no rige nada;
  - `workflow:publish` publicar, retirar y habilitar/deshabilitar. Pide step-up (proxy/stepup.py).
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere, usuario_actual
from app.services import wf_grafo as g
from app.services import wf_procesos as wf
from app.services.workflow import sembrar_reglas

router = APIRouter(prefix="/workflow", tags=["workflow-grafico"])
_lee = requiere("workflow:read")
_escribe = requiere("workflow:write")
_publica = requiere("workflow:publish")


class BorradorIn(BaseModel):
    desde: int | None = Field(None, description="Número de versión a clonar (por defecto, la publicada)")


class GuardarIn(BaseModel):
    grafo: dict
    layout: dict = {}
    nota: str | None = Field(None, max_length=300)
    revision: int


class PublicarIn(BaseModel):
    nota: str | None = Field(None, max_length=300)


class HabilitadoIn(BaseModel):
    habilitado: bool


def _proceso(db: Session, pid: int) -> models.WfProceso:
    p = db.get(models.WfProceso, pid)
    if not p:
        raise HTTPException(404, "Proceso no encontrado")
    return p


def _version(db: Session, vid: int) -> models.WfVersion:
    v = db.get(models.WfVersion, vid)
    if not v:
        raise HTTPException(404, "Versión no encontrada")
    return v


def _puede(user: Usuario) -> dict:
    return {"editar": user.puede("workflow:write"), "publicar": user.puede("workflow:publish")}


@router.get("/catalogo")
def catalogo(user: Usuario = Depends(_lee)):
    return {"tipos": list(g.TIPOS), "roles": list(g.ROLES), "resultados": list(g.RESULTADOS),
            "tiposDestinatario": list(g.TIPOS_DESTINATARIO), "operadores": g.OPERADORES, "puede": _puede(user)}


@router.get("/procesos")
def listar_procesos(db: Session = Depends(get_db), user: Usuario = Depends(_lee)):
    sembrar_reglas(db)
    wf.sincronizar_procesos(db)
    ps = db.query(models.WfProceso).order_by(models.WfProceso.modulo, models.WfProceso.id).all()
    return {"procesos": [wf.serial_proceso(p) for p in ps], "puede": _puede(user)}


@router.get("/procesos/{pid}")
def ver_proceso(pid: int, db: Session = Depends(get_db), user: Usuario = Depends(_lee)):
    return {**wf.serial_proceso(_proceso(db, pid), con_versiones=True), "puede": _puede(user)}


@router.post("/procesos/{pid}/borrador", status_code=201)
def nuevo_borrador(pid: int, data: BorradorIn, db: Session = Depends(get_db), user: Usuario = Depends(_escribe)):
    v = wf.crear_borrador(db, _proceso(db, pid), user.username, data.desde)
    db.commit()
    return wf.serial_version(v)


@router.get("/versiones/{vid}")
def ver_version(vid: int, db: Session = Depends(get_db), user: Usuario = Depends(_lee)):
    return {**wf.serial_version(_version(db, vid)), "puede": _puede(user)}


@router.put("/versiones/{vid}")
def guardar(vid: int, data: GuardarIn, db: Session = Depends(get_db), user: Usuario = Depends(_escribe)):
    """Autosave del borrador. Guarda aunque el grafo tenga errores (se está editando): los devuelve en
    `problemas` para mostrarlos sobre los nodos."""
    v = wf.guardar_borrador(db, _version(db, vid), data.grafo, data.layout, data.nota, data.revision, user.username)
    db.commit()
    return wf.serial_version(v)


@router.delete("/versiones/{vid}", status_code=204)
def descartar(vid: int, db: Session = Depends(get_db), _=Depends(_escribe)):
    wf.descartar_borrador(db, _version(db, vid))
    db.commit()


@router.post("/versiones/{vid}/publicar")
def publicar(vid: int, data: PublicarIn, db: Session = Depends(get_db), user: Usuario = Depends(_publica)):
    v = wf.publicar(db, _version(db, vid), user.username, data.nota)
    db.commit()
    return wf.serial_version(v)


@router.post("/versiones/{vid}/retirar")
def retirar(vid: int, db: Session = Depends(get_db), user: Usuario = Depends(_publica)):
    v = wf.retirar(db, _version(db, vid), user.username)
    db.commit()
    return wf.serial_version(v)


@router.post("/procesos/{pid}/habilitado")
def habilitado(pid: int, data: HabilitadoIn, db: Session = Depends(get_db), user: Usuario = Depends(_publica)):
    p = wf.habilitar(db, _proceso(db, pid), data.habilitado, user.username)
    db.commit()
    return wf.serial_proceso(p)


@router.get("/comparar")
def comparar(a: int = Query(..., description="id de la versión anterior"),
             b: int = Query(..., description="id de la versión nueva"),
             db: Session = Depends(get_db), _=Depends(_lee)):
    va, vb = _version(db, a), _version(db, b)
    if va.proceso_id != vb.proceso_id:
        raise HTTPException(422, "Sólo se comparan versiones del mismo proceso.")
    return {"a": wf.serial_version_resumen(va), "b": wf.serial_version_resumen(vb),
            "diff": g.comparar(va.grafo, vb.grafo)}
