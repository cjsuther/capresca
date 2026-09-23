"""Aviso de Tesorería con el resultado de los desembolsos (API interna, no pasa por el gateway).

CONFIRMADO → el contrato se desembolsa (asiento + actividad) y pasa a ACTIVO. Se aplica aunque venga de un
lote anterior: si la plata salió, el contrato tiene que quedar activo.
FALLIDO / EXCLUIDO / RECHAZADO → el contrato sigue A_LIQUIDAR, queda OBSERVADO con el motivo y se puede
volver a liquidar. Un aviso de un lote que ya no es el vigente del contrato no lo toca.
Idempotente: el mismo aviso dos veces no desembolsa dos veces.
"""
from __future__ import annotations

import hmac
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models_productos as m
from app.api.contratos import _desembolsar, _set_desembolso, desembolso_info
from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/internal/creditos/tesoreria", tags=["internal"])
FALLAS = {"FALLIDO", "EXCLUIDO", "RECHAZADO"}
TESORERIA = SimpleNamespace(username="tesoreria")


def api_tesoreria(x_api_key: str | None = Header(None, alias="X-Api-Key")) -> None:
    clave = get_settings().tesoreria_internal_api_key
    if not clave or not x_api_key or not hmac.compare_digest(x_api_key, clave):
        raise HTTPException(401, "API interna: clave inválida.")


class PagoAviso(BaseModel):
    referencia_externa: str
    estado: str
    motivo: str = ""
    id_operacion_ib: str = ""
    monto: float = 0


class Aviso(BaseModel):
    lote: str
    origen: str = "CREDITOS"
    referencia_origen: str = ""
    simulado: bool = False
    pagos: list[PagoAviso]


@router.post("/resultado", dependencies=[Depends(api_tesoreria)])
def resultado(aviso: Aviso, db: Session = Depends(get_db)):
    activados, observados, ignorados = [], [], []
    for p in aviso.pagos:
        c = db.query(m.PPContrato).filter_by(id=p.referencia_externa).with_for_update().first()
        if c is None:
            ignorados.append(p.referencia_externa); continue
        if p.estado == "CONFIRMADO":
            if c.estado == "A_LIQUIDAR":
                _desembolsar(db, c, TESORERIA)
                _set_desembolso(c, estado="CONFIRMADO", lote=aviso.lote, motivo="",
                                id_operacion_ib=p.id_operacion_ib, simulado=aviso.simulado)
                db.commit()
                activados.append(c.numero_contrato)
            else:
                db.rollback(); ignorados.append(c.numero_contrato)        # ya activo: aviso repetido
        elif p.estado in FALLAS:
            des = desembolso_info(c)
            if c.estado == "A_LIQUIDAR" and des.get("estado") == "EN_TESORERIA" and des.get("lote") == aviso.lote:
                _set_desembolso(c, estado="OBSERVADO", resultado=p.estado, intentos=int(des.get("intentos", 0)) + 1,
                                motivo=(p.motivo or f"Pago {p.estado.lower()} en Tesorería")[:300])
                db.commit()
                observados.append(c.numero_contrato)
            else:
                db.rollback(); ignorados.append(c.numero_contrato)
        else:
            db.rollback(); ignorados.append(c.numero_contrato)
    return {"activados": activados, "observados": observados, "ignorados": ignorados}
