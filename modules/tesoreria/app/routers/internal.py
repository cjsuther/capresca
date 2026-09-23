"""API interna: los módulos de origen (Créditos, Conciliación) mandan lotes de pagos. No sale del gateway."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import api_interna
from app.services import lotes as svc

router = APIRouter(prefix="/internal/tesoreria", tags=["internal"], dependencies=[Depends(api_interna)])


class PagoIn(BaseModel):
    referencia_externa: str
    beneficiario: str
    documento: str = ""
    cbu: str
    monto: float
    concepto: str = ""


class LoteIn(BaseModel):
    origen: str
    referencia_origen: str
    descripcion: str = ""
    callback_url: str | None = None      # dónde avisar el resultado de cada pago
    usuario: str = "sistema"             # quién lo generó en el módulo de origen (cuatro-ojos)
    pagos: list[PagoIn] = Field(min_length=1, max_length=2000)


@router.post("/lotes", status_code=201)
def recibir_lote(data: LoteIn, db: Session = Depends(get_db)):
    """Alta idempotente por (origen, referencia_origen): reenviar el mismo lote devuelve el existente."""
    if data.origen == "MANUAL":
        raise HTTPException(422, "Los lotes manuales se cargan desde la pantalla de Tesorería.")
    lote, rechazados, ya_existia = svc.crear_lote(
        db, origen=data.origen, referencia_origen=data.referencia_origen, descripcion=data.descripcion,
        pagos=[p.model_dump() for p in data.pagos], usuario=data.usuario, callback_url=data.callback_url)
    return {"codigo": lote.codigo, "id": lote.id, "estado": lote.estado, "ya_existia": ya_existia,
            "rechazados": rechazados, "pagos": [{"referencia_externa": p.referencia_externa, "estado": p.estado}
                                                for p in lote.pagos]}


@router.get("/lotes/{codigo}")
def estado_lote(codigo: str, db: Session = Depends(get_db)):
    lote = db.query(models.Lote).filter_by(codigo=codigo).first()
    if not lote:
        raise HTTPException(404, "Lote no encontrado")
    return {**svc.resumen(lote), "pagos": [{"referencia_externa": p.referencia_externa, "estado": p.estado,
                                            "motivo": p.motivo} for p in lote.pagos]}
