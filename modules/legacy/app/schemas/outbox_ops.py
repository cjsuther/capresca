"""
Schemas de las operaciones de escritura hacia el legacy.

Estas operaciones NO se aplican en caliente: entran al outbox y se devuelve 202.
El payload se persiste tal cual (JSONB) y lo aplica el drainer (dry-run en Fase 3,
real en Fase 4).
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class FormaPago(BaseModel):
    moneda: str = "$"
    importe: Decimal
    origen: Optional[str] = None
    sno_recibo: Optional[int] = None


class AplicarPagoRequest(BaseModel):
    """
    Aplicar un pago en caja: INSERT cajapagos + cajaforpag y REPLACE cajaliq.pagado=.T.
    """
    no_recibo: int = Field(..., description="Número de recibo (clave de idempotencia)")
    cod_agencia: str
    fecha_pago: date
    total: Decimal
    origen: Optional[str] = None
    cajero: Optional[str] = None
    formas_pago: list[FormaPago] = []
    # Liquidaciones (cajaliq) a marcar como pagadas: claves naturales
    liquidaciones: list[dict] = Field(
        default=[],
        description="Lista de {cod_agencia, cod_juego, no_sorteo} a marcar pagado",
    )


class AnularPagoRequest(BaseModel):
    """
    Anular un pago/cobro: REPLACE cajaforpag.anulado, revertir cajaliq/cajacreseg.
    """
    motivo: Optional[str] = None


class ConsolidarCreditosRequest(BaseModel):
    """
    Consolidar créditos / actualizar mora: REPLACE en maecuotas.
    """
    fecha: date
    detalle: Optional[dict] = None


class OutboxEnqueueResponse(BaseModel):
    outbox_id: int
    status: str
    idempotency_key: str
    created: bool  # False si ya existía (idempotente)
