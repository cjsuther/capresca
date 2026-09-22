"""Consulta del registro de auditoría (sólo lectura, detrás del gateway)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere
from app.services import registro

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("/eventos")
def listar(usuario: str = "", modulo: str = "", operacion: str = "", entidad: str = "",
           entidad_id: str = "", texto: str = "", desde: date | None = None, hasta: date | None = None,
           solo_errores: bool = False, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
           db: Session = Depends(get_db), _u: Usuario = Depends(requiere("eventos:read"))):
    return registro.buscar(db, usuario=usuario, modulo=modulo, operacion=operacion, entidad=entidad,
                           entidad_id=entidad_id, texto=texto, desde=desde, hasta=hasta,
                           solo_errores=solo_errores, limit=limit, offset=offset)


@router.get("/eventos/resumen")
def resumen(db: Session = Depends(get_db), _u: Usuario = Depends(requiere("eventos:read"))):
    """Para los filtros y los indicadores de la pantalla."""
    por = lambda col: [{"valor": v, "cantidad": n} for v, n in db.execute(  # noqa: E731
        select(col, func.count()).group_by(col).order_by(func.count().desc()).limit(50)).all() if v]
    total = db.scalar(select(func.count()).select_from(models.Evento)) or 0
    ultimo = db.scalar(select(func.max(models.Evento.fecha)))
    return {"total": total, "ultimo": ultimo.isoformat() if ultimo else None,
            "modulos": por(models.Evento.modulo), "usuarios": por(models.Evento.usuario),
            "operaciones": por(models.Evento.operacion), "entidades": por(models.Evento.entidad),
            "retencionDias": settings.retencion_dias}


@router.get("/eventos/{evento_id}")
def ver(evento_id: int, db: Session = Depends(get_db), _u: Usuario = Depends(requiere("eventos:read"))):
    e = db.get(models.Evento, evento_id)
    if not e:
        raise HTTPException(404, "Evento no encontrado")
    relacionados = []
    if e.request_id:
        relacionados = [registro.serial(x) for x in db.scalars(
            select(models.Evento).where(models.Evento.request_id == e.request_id,
                                        models.Evento.id != e.id).order_by(models.Evento.id)).all()]
    return {**registro.serial(e), "relacionados": relacionados}


@router.get("/registros/{modulo}/{entidad}/{entidad_id}")
def historia(modulo: str, entidad: str, entidad_id: str, db: Session = Depends(get_db),
             _u: Usuario = Depends(requiere("eventos:read"))):
    """Todo lo que le pasó a un registro concreto, del más nuevo al más viejo."""
    return registro.buscar(db, modulo=modulo, entidad=entidad, entidad_id=entidad_id, limit=500)
