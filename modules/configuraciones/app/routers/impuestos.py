"""Impuestos generales (IVA, IIBB, sellado, percepciones). Créditos los usa en el componente TAX de
sus productos (guarda la alícuota en la versión, así un cambio acá no altera contratos ya firmados)."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import requiere, usuario_actual

router = APIRouter(prefix="/impuestos", tags=["impuestos"], dependencies=[Depends(usuario_actual)])
_escribe = requiere("impuestos:write")

TIPOS = ("IVA", "IIBB", "SELLADO", "PERCEPCION", "RETENCION", "OTRO")
BASES = ("INTERES", "CARGOS", "CUOTA", "CAPITAL", "TOTAL")


class ImpuestoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=120)
    tipo: str = "IVA"
    alicuota: float = Field(0, ge=0, le=100)
    base: str = "INTERES"
    cuenta_contable: str = Field("", max_length=12)
    jurisdiccion: str = Field("", max_length=40)
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    activo: bool = True


def serial(i: models.Impuesto) -> dict:
    return {
        "id": i.id, "codigo": i.codigo, "nombre": i.nombre, "tipo": i.tipo,
        "alicuota": float(i.alicuota), "base": i.base, "cuenta_contable": i.cuenta_contable,
        "jurisdiccion": i.jurisdiccion,
        "vigente_desde": i.vigente_desde.isoformat() if i.vigente_desde else None,
        "vigente_hasta": i.vigente_hasta.isoformat() if i.vigente_hasta else None,
        "activo": i.activo,
    }


def listar_impuestos(db: Session, estado: str) -> list[dict]:
    q = db.query(models.Impuesto)
    if estado == "activos":
        q = q.filter(models.Impuesto.activo.is_(True))
    return [serial(i) for i in q.order_by(models.Impuesto.codigo).all()]


def _validar(data: ImpuestoIn) -> dict:
    if data.tipo not in TIPOS:
        raise HTTPException(422, f"Tipo inválido. Opciones: {', '.join(TIPOS)}.")
    if data.base not in BASES:
        raise HTTPException(422, f"Base inválida. Opciones: {', '.join(BASES)}.")
    if data.vigente_desde and data.vigente_hasta and data.vigente_hasta < data.vigente_desde:
        raise HTTPException(422, "La vigencia termina antes de empezar.")
    return {**data.model_dump(), "codigo": data.codigo.strip().upper(), "nombre": data.nombre.strip(),
            "alicuota": Decimal(str(data.alicuota))}


def _obtener(db: Session, imp_id: int) -> models.Impuesto:
    i = db.get(models.Impuesto, imp_id)
    if not i:
        raise HTTPException(404, "Impuesto no encontrado")
    return i


@router.get("")
def listar(estado: str = Query("todos", pattern="^(activos|todos)$"), db: Session = Depends(get_db)):
    items = listar_impuestos(db, estado)
    return {"items": items, "total": len(items)}


@router.post("", status_code=201, dependencies=[Depends(_escribe)])
def crear(data: ImpuestoIn, db: Session = Depends(get_db)):
    valores = _validar(data)
    if db.query(models.Impuesto).filter_by(codigo=valores["codigo"]).first():
        raise HTTPException(409, "Ya existe un impuesto con ese código")
    i = models.Impuesto(**valores)
    db.add(i); db.commit(); db.refresh(i)
    return serial(i)


@router.put("/{imp_id}", dependencies=[Depends(_escribe)])
def editar(imp_id: int, data: ImpuestoIn, db: Session = Depends(get_db)):
    i = _obtener(db, imp_id)
    valores = _validar(data)
    otro = db.query(models.Impuesto).filter_by(codigo=valores["codigo"]).first()
    if otro and otro.id != i.id:
        raise HTTPException(409, "Ya existe un impuesto con ese código")
    for k, v in valores.items():
        setattr(i, k, v)
    db.commit(); db.refresh(i)
    return serial(i)


@router.post("/{imp_id}/baja", dependencies=[Depends(_escribe)])
def baja(imp_id: int, db: Session = Depends(get_db)):
    i = _obtener(db, imp_id)
    i.activo = False; db.commit()
    return serial(i)


@router.post("/{imp_id}/reactivar", dependencies=[Depends(_escribe)])
def reactivar(imp_id: int, db: Session = Depends(get_db)):
    i = _obtener(db, imp_id)
    i.activo = True; db.commit()
    return serial(i)
