"""Maestro de índices de referencia (Contabilidad → Índices).

Índices para tasas variables (BADLAR, política monetaria, UVA…). La tasa efectiva de un
producto de tasa variable = valor del índice + margen.
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app import models

router = APIRouter(prefix="/api/creditos/indices", tags=["indices"],
                   dependencies=[Depends(get_current_user)])


class IndiceIn(BaseModel):
    codigo: str
    nombre: str
    valor: float = 0
    fuente: str = ""
    fecha_valor: date | None = None
    activo: bool = True


def _serial(i: models.IndiceReferencia) -> dict:
    return {"id": i.id, "codigo": i.codigo, "nombre": i.nombre, "valor": float(i.valor),
            "fuente": i.fuente, "fecha_valor": str(i.fecha_valor) if i.fecha_valor else None,
            "activo": i.activo}


@router.get("")
def listar(estado: str = Query("todos"), db: Session = Depends(get_db)):
    q = db.query(models.IndiceReferencia)
    if estado == "activos":
        q = q.filter(models.IndiceReferencia.activo.is_(True))
    return {"items": [_serial(i) for i in q.order_by(models.IndiceReferencia.codigo).all()]}


@router.post("", status_code=201)
def crear(data: IndiceIn, db: Session = Depends(get_db)):
    if db.query(models.IndiceReferencia).filter_by(codigo=data.codigo.strip().upper()).first():
        raise HTTPException(409, "Ya existe un índice con ese código")
    i = models.IndiceReferencia(**{**data.model_dump(), "codigo": data.codigo.strip().upper(),
                                   "valor": Decimal(str(data.valor))})
    db.add(i); db.commit(); db.refresh(i)
    return _serial(i)


@router.put("/{ind_id}")
def editar(ind_id: int, data: IndiceIn, db: Session = Depends(get_db)):
    i = db.get(models.IndiceReferencia, ind_id)
    if not i:
        raise HTTPException(404, "Índice no encontrado")
    for k, v in data.model_dump().items():
        setattr(i, k, Decimal(str(v)) if k == "valor" else (v.strip().upper() if k == "codigo" else v))
    db.commit(); db.refresh(i)
    return _serial(i)


@router.post("/{ind_id}/baja")
def baja(ind_id: int, db: Session = Depends(get_db)):
    i = db.get(models.IndiceReferencia, ind_id)
    if not i:
        raise HTTPException(404, "Índice no encontrado")
    i.activo = False; db.commit(); return _serial(i)


@router.post("/{ind_id}/reactivar")
def reactivar(ind_id: int, db: Session = Depends(get_db)):
    i = db.get(models.IndiceReferencia, ind_id)
    if not i:
        raise HTTPException(404, "Índice no encontrado")
    i.activo = True; db.commit(); return _serial(i)
