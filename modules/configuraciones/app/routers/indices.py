"""Índices de referencia para tasas variables (BADLAR, TPM, UVA…). Créditos calcula la TNA de una
línea variable como índice + margen al simular, originar y en cada repricing."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import requiere, usuario_actual

router = APIRouter(prefix="/indices", tags=["indices"], dependencies=[Depends(usuario_actual)])
_escribe = requiere("indices:write")


class IndiceIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    nombre: str = Field(min_length=1, max_length=120)
    valor: float = Field(0, ge=0, le=1000)
    fuente: str = Field("", max_length=60)
    fecha_valor: date | None = None
    activo: bool = True


def serial(i: models.IndiceReferencia) -> dict:
    return {"id": i.id, "codigo": i.codigo, "nombre": i.nombre, "valor": float(i.valor),
            "fuente": i.fuente, "fecha_valor": i.fecha_valor.isoformat() if i.fecha_valor else None,
            "activo": i.activo}


def listar_indices(db: Session, estado: str) -> list[dict]:
    q = db.query(models.IndiceReferencia)
    if estado == "activos":
        q = q.filter(models.IndiceReferencia.activo.is_(True))
    return [serial(i) for i in q.order_by(models.IndiceReferencia.codigo).all()]


def _valores(data: IndiceIn) -> dict:
    return {**data.model_dump(), "codigo": data.codigo.strip().upper(), "nombre": data.nombre.strip(),
            "valor": Decimal(str(data.valor))}


def _obtener(db: Session, ind_id: int) -> models.IndiceReferencia:
    i = db.get(models.IndiceReferencia, ind_id)
    if not i:
        raise HTTPException(404, "Índice no encontrado")
    return i


@router.get("")
def listar(estado: str = Query("todos", pattern="^(activos|todos)$"), db: Session = Depends(get_db)):
    items = listar_indices(db, estado)
    return {"items": items, "total": len(items)}


@router.post("", status_code=201, dependencies=[Depends(_escribe)])
def crear(data: IndiceIn, db: Session = Depends(get_db)):
    valores = _valores(data)
    if db.query(models.IndiceReferencia).filter_by(codigo=valores["codigo"]).first():
        raise HTTPException(409, "Ya existe un índice con ese código")
    i = models.IndiceReferencia(**valores)
    db.add(i); db.commit(); db.refresh(i)
    return serial(i)


@router.put("/{ind_id}", dependencies=[Depends(_escribe)])
def editar(ind_id: int, data: IndiceIn, db: Session = Depends(get_db)):
    i = _obtener(db, ind_id)
    valores = _valores(data)
    otro = db.query(models.IndiceReferencia).filter_by(codigo=valores["codigo"]).first()
    if otro and otro.id != i.id:
        raise HTTPException(409, "Ya existe un índice con ese código")
    for k, v in valores.items():
        setattr(i, k, v)
    db.commit(); db.refresh(i)
    return serial(i)


@router.post("/{ind_id}/baja", dependencies=[Depends(_escribe)])
def baja(ind_id: int, db: Session = Depends(get_db)):
    i = _obtener(db, ind_id)
    i.activo = False; db.commit()
    return serial(i)


@router.post("/{ind_id}/reactivar", dependencies=[Depends(_escribe)])
def reactivar(ind_id: int, db: Session = Depends(get_db)):
    i = _obtener(db, ind_id)
    i.activo = True; db.commit()
    return serial(i)
