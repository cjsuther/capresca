"""Maestro de impuestos (Contabilidad → Impuestos).

ABM de impuestos generales del sistema (IVA, IIBB, sellado, percepciones). Otros módulos
—por ejemplo Configurar Créditos (componente TAX)— podrán referenciarlos.
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app import models

router = APIRouter(prefix="/api/creditos/impuestos", tags=["impuestos"],
                   dependencies=[Depends(get_current_user)])


class ImpuestoIn(BaseModel):
    codigo: str
    nombre: str
    tipo: str = "IVA"
    alicuota: float = 0
    base: str = "INTERES"
    cuenta_contable: str = ""
    jurisdiccion: str = ""
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    activo: bool = True


def _serial(i: models.Impuesto) -> dict:
    return {
        "id": i.id, "codigo": i.codigo, "nombre": i.nombre, "tipo": i.tipo,
        "alicuota": float(i.alicuota), "base": i.base, "cuenta_contable": i.cuenta_contable,
        "jurisdiccion": i.jurisdiccion,
        "vigente_desde": str(i.vigente_desde) if i.vigente_desde else None,
        "vigente_hasta": str(i.vigente_hasta) if i.vigente_hasta else None,
        "activo": i.activo,
    }


@router.get("")
def listar(estado: str = Query("todos", description="activos | todos"),
           db: Session = Depends(get_db)):
    q = db.query(models.Impuesto)
    if estado == "activos":
        q = q.filter(models.Impuesto.activo.is_(True))
    items = [_serial(i) for i in q.order_by(models.Impuesto.codigo).all()]
    return {"items": items, "total": len(items)}


@router.post("", status_code=201)
def crear(data: ImpuestoIn, db: Session = Depends(get_db)):
    if db.query(models.Impuesto).filter_by(codigo=data.codigo.strip().upper()).first():
        raise HTTPException(409, "Ya existe un impuesto con ese código")
    i = models.Impuesto(**{**data.model_dump(), "codigo": data.codigo.strip().upper(),
                           "alicuota": Decimal(str(data.alicuota))})
    db.add(i); db.commit(); db.refresh(i)
    return _serial(i)


@router.put("/{imp_id}")
def editar(imp_id: int, data: ImpuestoIn, db: Session = Depends(get_db)):
    i = db.get(models.Impuesto, imp_id)
    if not i:
        raise HTTPException(404, "Impuesto no encontrado")
    for k, v in data.model_dump().items():
        setattr(i, k, Decimal(str(v)) if k == "alicuota" else (v.strip().upper() if k == "codigo" else v))
    db.commit(); db.refresh(i)
    return _serial(i)


@router.post("/{imp_id}/baja")
def baja(imp_id: int, db: Session = Depends(get_db)):
    i = db.get(models.Impuesto, imp_id)
    if not i:
        raise HTTPException(404, "Impuesto no encontrado")
    i.activo = False; db.commit(); return _serial(i)


@router.post("/{imp_id}/reactivar")
def reactivar(imp_id: int, db: Session = Depends(get_db)):
    i = db.get(models.Impuesto, imp_id)
    if not i:
        raise HTTPException(404, "Impuesto no encontrado")
    i.activo = True; db.commit(); return _serial(i)
