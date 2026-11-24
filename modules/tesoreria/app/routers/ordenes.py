"""Órdenes de pago de créditos (detrás del gateway: permisos `tesoreria:lotes:*`)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere, usuario_actual
from app.services import creditos_central as creditos, ordenes as svc

router = APIRouter(prefix="/ordenes-pago", tags=["ordenes-pago"])


class OrdenIn(BaseModel):
    actos: list[str] = Field(min_length=1)       # claves de /disponibles (una por resolución / disposición)
    numero: StrictInt | None = None              # N° elegido para el año en curso; sin él, el mayor + 1


class AnularIn(BaseModel):
    motivo: str = ""


def _orden(db: Session, orden_id: int) -> models.OrdenPago:
    op = db.get(models.OrdenPago, orden_id)
    if op is None:
        raise HTTPException(404, "Orden de pago no encontrada")
    return op


@router.get("")
def listar(estado: str | None = Query(None), db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    return {"items": [svc.resumen(op) for op in svc.listar(db, estado)]}


@router.get("/disponibles")
def disponibles(_u: Usuario = Depends(usuario_actual)):
    """Resoluciones / disposiciones con lotes de créditos que todavía no están en una orden de pago."""
    return creditos.disponibles()


@router.get("/proximo-numero")
def proximo_numero(db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    """El N° que se sugiere para la próxima orden del año en curso (el usuario lo puede cambiar)."""
    return svc.proximo_numero(db)


@router.get("/{orden_id}")
def ver(orden_id: int, db: Session = Depends(get_db), user: Usuario = Depends(usuario_actual)):
    return svc.detalle(_orden(db, orden_id), user)


@router.post("", status_code=201)
def confeccionar(data: OrdenIn, db: Session = Depends(get_db), user: Usuario = Depends(requiere("lotes:write"))):
    return svc.detalle(svc.confeccionar(db, data.actos, user, data.numero), user)


@router.post("/{orden_id}/anular")
def anular(orden_id: int, data: AnularIn, db: Session = Depends(get_db),
           user: Usuario = Depends(requiere("lotes:write"))):
    return svc.detalle(svc.anular(db, _orden(db, orden_id), data.motivo, user), user)
