"""API interna: los módulos mandan sus TRANSACCIONES (nunca asientos).

Contabilidad decide cómo se registra cada una según su definición. Si no hay definición, la
transacción queda pendiente de configuración acá: el módulo de origen no tiene que saber de cuentas.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import api_interna
from app.services import motor

router = APIRouter(prefix="/internal/contabilidad", tags=["internal"], dependencies=[Depends(api_interna)])


class TransaccionIn(BaseModel):
    modulo: str = Field(min_length=1, max_length=30)
    tipo: str = Field(min_length=1, max_length=60)        # DESEMBOLSO, COBRANZA_CUOTA, PAGO_AGENCIA…
    referencia: str = Field(min_length=1, max_length=80)  # id/numero en el módulo de origen
    fecha: date
    moneda: str = "ARS"
    descripcion: str = ""
    usuario: str = ""
    # Importes y datos del evento. Las definiciones arman el asiento con estos campos:
    #   {"capital": 100000, "interes": 5200, "iva": 1092, "comprobante": {...}}
    datos: dict = Field(default_factory=dict)


@router.post("/transacciones", status_code=201)
def recibir(data: TransaccionIn, db: Session = Depends(get_db)):
    """Alta idempotente por (módulo, tipo, referencia): reenviar lo mismo no duplica el asiento."""
    t, ya_existia = motor.recibir(db, data.model_dump())
    return {"id": t.id, "estado": t.estado, "motivo": t.motivo, "asientoId": t.asiento_id,
            "ya_existia": ya_existia}


@router.get("/transacciones/{modulo}/{tipo}/{referencia}")
def estado(modulo: str, tipo: str, referencia: str, db: Session = Depends(get_db)):
    t = db.scalar(select(models.Transaccion).where(models.Transaccion.modulo == modulo,
                                                   models.Transaccion.tipo == tipo,
                                                   models.Transaccion.referencia == referencia))
    if not t:
        raise HTTPException(404, "Transacción no registrada en Contabilidad")
    return {"id": t.id, "estado": t.estado, "motivo": t.motivo, "asientoId": t.asiento_id,
            "fecha": t.fecha.isoformat()}
