"""Módulo Mesa de entradas: turnos de atención y tablero de cola."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from fastapi.responses import Response

from app.core.database import get_db
from app.deps import get_current_user, requiere_perfil
from app.services import mesa as svc
from app.services import tramites as tsvc
from app import models, schemas

router = APIRouter(prefix="/api/creditos/mesa", tags=["mesa"],
                   dependencies=[Depends(get_current_user)])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/tramites/tipos")
def tramite_tipos(db: Session = Depends(get_db)):
    """Catálogo de tipos de trámite histórico (VFP: tipotram)."""
    return tsvc.tipos(db)


@router.get("/oficinas")
def oficinas(db: Session = Depends(get_db)):
    """Maestro de oficinas/dependencias (VFP: oficinas)."""
    return tsvc.oficinas(db)


@router.get("/tramites")
def tramites(tipo: str | None = None, estado: str | None = None, anio: int | None = None,
             q: str | None = None, solo_expedientes: bool = False,
             limit: int = 25, offset: int = 0, db: Session = Depends(get_db)):
    """Consulta paginada de trámites de Mesa de Entradas (VFP: 520100003constram).
    `solo_expedientes=true` filtra a los expedientes (tipo E*)."""
    return tsvc.consultar(db, tipo=tipo, estado=estado, anio=anio, q=q,
                          solo_expedientes=solo_expedientes, limit=limit, offset=offset)


@router.get("/tramites/{tramite_id}/pases")
def tramite_pases(tramite_id: int, db: Session = Depends(get_db)):
    """Historial de pases de un trámite (VFP: pasesexptes)."""
    r = tsvc.pases_de_tramite(db, tramite_id)
    if r is None:
        raise HTTPException(404, "Trámite no encontrado")
    return r


@router.get("/tramites/ingresados")
def tramites_ingresados(desde: date | None = None, hasta: date | None = None,
                        db: Session = Depends(get_db)):
    """Informe de trámites ingresados por tipo (VFP: tramitesdiarios / parte diario)."""
    return tsvc.ingresados_por_periodo(db, desde, hasta)

_perfil_mesa = requiere_perfil("AU", "PE", "PA", "NT")  # mesa/atención o ADMG


@router.get("/tipos-tramite", response_model=list[schemas.TipoTramiteOut])
def tipos_tramite(db: Session = Depends(get_db)):
    return db.scalars(select(models.TipoTramite).where(
        models.TipoTramite.activo).order_by(models.TipoTramite.nombre)).all()


@router.post("/turnos", response_model=schemas.TurnoOut, status_code=201)
def generar_turno(data: schemas.TurnoCreate, db: Session = Depends(get_db)):
    try:
        return svc.generar_turno(db, tipo_tramite_id=data.tipo_tramite_id,
                                 cliente_nombre=data.cliente_nombre,
                                 cliente_cuil=data.cliente_cuil, fecha=data.fecha)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))


@router.get("/turnos", response_model=list[schemas.TurnoOut])
def listar_turnos(
    fecha: date = Query(default_factory=date.today),
    estado: str | None = None,
    db: Session = Depends(get_db),
):
    qy = select(models.Turno).where(models.Turno.fecha == fecha)
    if estado:
        qy = qy.where(models.Turno.estado == estado)
    return db.scalars(qy.order_by(models.Turno.numero)).all()


@router.get("/tablero", response_model=schemas.Tablero)
def tablero(fecha: date = Query(default_factory=date.today), db: Session = Depends(get_db)):
    return svc.tablero(db, fecha)


@router.post("/llamar", response_model=schemas.TurnoOut)
def llamar_siguiente(req: schemas.LlamarRequest, db: Session = Depends(get_db),
                     _u: models.Usuario = Depends(_perfil_mesa)):
    turno = svc.llamar_siguiente(db, box=req.box, fecha=req.fecha,
                                 tipo_tramite_id=req.tipo_tramite_id)
    if not turno:
        raise HTTPException(404, "No hay turnos en espera")
    return turno


@router.post("/turnos/{turno_id}/atender", response_model=schemas.TurnoOut)
def atender(turno_id: int, db: Session = Depends(get_db),
            _u: models.Usuario = Depends(_perfil_mesa)):
    try:
        return svc.atender_turno(db, turno_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/turnos/{turno_id}/cancelar", response_model=schemas.TurnoOut)
def cancelar(turno_id: int, db: Session = Depends(get_db),
             _u: models.Usuario = Depends(_perfil_mesa)):
    try:
        return svc.cancelar_turno(db, turno_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))
