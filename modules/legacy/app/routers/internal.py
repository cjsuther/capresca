"""
Router interno (contenedor-a-contenedor, NO expuesto por el proxy).
Lo consumen los demás módulos para leer del legacy (mirror) y encolar escrituras.
Las lecturas concretas se agregan en la Fase 1; las escrituras (outbox) en la Fase 3.

Toda escritura entra al outbox y devuelve 202 (nunca toca las DBF en caliente).
El kill switch (INTEGRATION_ENABLED=false) hace que las escrituras devuelvan 410.
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.dependencies.auth import verify_api_key
from app.legacy_catalog import READ_ONLY_TABLES
from app.models.outbox import LegacyOutbox
from app.models.mirror_juegos import MirrorMaeagencias, MirrorMaejuegos
from app.models.mirror_caja import (
    MirrorCajaliq,
    MirrorCajapagos,
    MirrorCajaforpag,
    MirrorCajacreseg,
)
from app.schemas.outbox_ops import (
    AplicarPagoRequest,
    AnularPagoRequest,
    ConsolidarCreditosRequest,
    OutboxEnqueueResponse,
)
from app.services import outbox_service, smb_health

router = APIRouter(prefix="/internal/legacy", dependencies=[Depends(verify_api_key)])


def _ensure_writes_enabled():
    """Kill switch: con la integración apagada, no se aceptan escrituras."""
    if not settings.integration_enabled:
        raise HTTPException(status_code=410, detail="Integración legacy apagada (INTEGRATION_ENABLED=false)")


@router.get("/ping")
def ping():
    """Sonda interna: estado básico de la integración para los consumidores."""
    return {
        "service": "legacy",
        "integration_enabled": settings.integration_enabled,
        "write_mode": settings.write_mode,
        "smb_available": smb_health.is_available(),
    }


def _enqueue_response(row, created, response: Response) -> OutboxEnqueueResponse:
    response.status_code = 202
    return OutboxEnqueueResponse(
        outbox_id=row.id,
        status=row.status,
        idempotency_key=row.idempotency_key,
        created=created,
    )


@router.post("/pagos", response_model=OutboxEnqueueResponse, status_code=202)
def encolar_aplicar_pago(
    req: AplicarPagoRequest,
    response: Response,
    db: Session = Depends(get_db),
    x_origin_module: Optional[str] = Header(None),
    x_user_id: Optional[int] = Header(None),
):
    """Encola la aplicación de un pago en caja (idempotente por no_recibo)."""
    _ensure_writes_enabled()
    row, created = outbox_service.enqueue(
        db,
        operation="aplicar_pago",
        database="caja",
        idempotency_key=f"aplicar_pago:{req.no_recibo}",
        payload=req.model_dump(mode="json"),
        origin_module=x_origin_module,
        origin_user_id=x_user_id,
    )
    return _enqueue_response(row, created, response)


@router.post("/pagos/{no_recibo}/anular", response_model=OutboxEnqueueResponse, status_code=202)
def encolar_anular_pago(
    no_recibo: int,
    req: AnularPagoRequest,
    response: Response,
    db: Session = Depends(get_db),
    x_origin_module: Optional[str] = Header(None),
    x_user_id: Optional[int] = Header(None),
):
    """Encola la anulación de un pago/cobro (idempotente por no_recibo)."""
    _ensure_writes_enabled()
    payload = req.model_dump(mode="json")
    payload["no_recibo"] = no_recibo
    row, created = outbox_service.enqueue(
        db,
        operation="anular_pago",
        database="caja",
        idempotency_key=f"anular_pago:{no_recibo}",
        payload=payload,
        origin_module=x_origin_module,
        origin_user_id=x_user_id,
    )
    return _enqueue_response(row, created, response)


@router.post("/creditos/consolidar", response_model=OutboxEnqueueResponse, status_code=202)
def encolar_consolidar_creditos(
    req: ConsolidarCreditosRequest,
    response: Response,
    db: Session = Depends(get_db),
    x_origin_module: Optional[str] = Header(None),
    x_user_id: Optional[int] = Header(None),
):
    """Encola la consolidación de créditos / actualización de mora (maecuotas)."""
    _ensure_writes_enabled()
    if "maecuotas" in READ_ONLY_TABLES:  # defensa: nunca tablas de solo lectura
        raise HTTPException(status_code=409, detail="Tabla de solo lectura")
    row, created = outbox_service.enqueue(
        db,
        operation="consolidar_creditos",
        database="creditos",
        idempotency_key=f"consolidar_creditos:{req.fecha.isoformat()}",
        payload=req.model_dump(mode="json"),
        origin_module=x_origin_module,
        origin_user_id=x_user_id,
    )
    return _enqueue_response(row, created, response)


# ── Lecturas (sirven del mirror; funcionan aunque la integración esté apagada) ──

def _to_float(v):
    return float(v) if v is not None else None


@router.get("/agencias")
def read_agencias(db: Session = Depends(get_db)):
    rows = db.query(MirrorMaeagencias).order_by(MirrorMaeagencias.cod_agencia).all()
    return [{"cod_agencia": r.cod_agencia, "titular": r.titular} for r in rows]


@router.get("/juegos")
def read_juegos(db: Session = Depends(get_db)):
    rows = db.query(MirrorMaejuegos).order_by(MirrorMaejuegos.cod_juego).all()
    return [{"cod_juego": r.cod_juego, "descripcion": r.descripcion, "modalidad": r.modalidad} for r in rows]


@router.get("/cajaliq")
def read_cajaliq(
    db: Session = Depends(get_db),
    agencia: Optional[str] = Query(None),
    pagado: Optional[bool] = Query(None),
):
    q = db.query(MirrorCajaliq)
    if agencia is not None:
        q = q.filter(MirrorCajaliq.cod_agencia == agencia)
    if pagado is not None:
        q = q.filter(MirrorCajaliq.pagado.is_(pagado))
    rows = q.all()
    return [
        {
            "cod_agencia": r.cod_agencia, "cod_juego": r.cod_juego, "no_sorteo": r.no_sorteo,
            "importe": _to_float(r.importe), "intereses": _to_float(r.intereses),
            "pagado": r.pagado, "fecha_pago": r.fecha_pago.isoformat() if r.fecha_pago else None,
            "no_recibo": r.no_recibo,
        }
        for r in rows
    ]


@router.get("/pagos")
def read_pagos(
    db: Session = Depends(get_db),
    fecha: Optional[date] = Query(None),
    agencia: Optional[str] = Query(None),
):
    q = db.query(MirrorCajapagos)
    if fecha is not None:
        q = q.filter(MirrorCajapagos.fecha_pago == fecha)
    if agencia is not None:
        q = q.filter(MirrorCajapagos.cod_agencia == agencia)
    rows = q.all()
    return [
        {
            "no_recibo": r.no_recibo, "cod_agencia": r.cod_agencia,
            "fecha_pago": r.fecha_pago.isoformat() if r.fecha_pago else None,
            "origen": r.origen, "total": _to_float(r.total), "cajero": r.cajero,
        }
        for r in rows
    ]


@router.get("/formas-pago")
def read_formas_pago(
    db: Session = Depends(get_db),
    no_recibo: Optional[int] = Query(None),
):
    q = db.query(MirrorCajaforpag)
    if no_recibo is not None:
        q = q.filter(MirrorCajaforpag.no_recibo == no_recibo)
    rows = q.all()
    return [
        {
            "no_recibo": r.no_recibo, "sno_recibo": r.sno_recibo, "moneda": r.moneda,
            "origen": r.origen, "fecha_pago": r.fecha_pago.isoformat() if r.fecha_pago else None,
            "anulado": r.anulado,
        }
        for r in rows
    ]


@router.get("/creditos-seguros")
def read_creditos_seguros(
    db: Session = Depends(get_db),
    fecha: Optional[date] = Query(None),
):
    q = db.query(MirrorCajacreseg)
    if fecha is not None:
        q = q.filter(MirrorCajacreseg.fecha_pago == fecha)
    rows = q.all()
    return [
        {
            "nrecibo": r.nrecibo, "recofi": r.recofi, "origen": r.origen,
            "fecha_pago": r.fecha_pago.isoformat() if r.fecha_pago else None,
            "via_pago": r.via_pago, "usuario_pago": r.usuario_pago,
        }
        for r in rows
    ]


@router.get("/outbox/{outbox_id}")
def estado_outbox(outbox_id: int, db: Session = Depends(get_db)):
    """Permite al módulo origen consultar el estado de su escritura encolada."""
    row = db.query(LegacyOutbox).filter(LegacyOutbox.id == outbox_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Operación no encontrada en el outbox")
    return {
        "outbox_id": row.id,
        "operation": row.operation,
        "status": row.status,
        "attempts": row.attempts,
        "last_error": row.last_error,
        "created_at": row.created_at,
        "applied_at": row.applied_at,
    }
