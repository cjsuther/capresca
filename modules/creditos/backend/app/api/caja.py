"""Caja del circuito de créditos: recibo en PDF y pendientes de cobro.

La operatoria de caja de CCyPP (cobranza de ventanilla, cola, control y cierre) no se migró a
Portezuelo; los cobros de los contratos van por el servicing (`/contratos`). Queda `services/caja`
para la cancelación anticipada de créditos migrados (`/creditos/{id}/cancelar`).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app.services import caja as svc
from app.reports.pdf import recibo_pdf, pendientes_cobro_pdf
from app import models, schemas

router = APIRouter(prefix="/api/creditos/caja", tags=["caja"],
                   dependencies=[Depends(get_current_user)])


def _recibo_detalle(db: Session, r: models.Recibo) -> schemas.ReciboDetalle:
    cliente = db.get(models.Cliente, r.cliente_id)
    pagos = db.scalars(select(models.PagoCuota).where(
        models.PagoCuota.recibo_id == r.id)).all()
    return schemas.ReciboDetalle(
        **schemas.ReciboOut.model_validate(r).model_dump(),
        cliente_nombre=cliente.apellido_nombre if cliente else "",
        pagos=[schemas.PagoCuotaOut.model_validate(p) for p in pagos],
    )


@router.get("/recibos/{recibo_id}/pdf")
def recibo_pdf_endpoint(recibo_id: int, db: Session = Depends(get_db)):
    r = db.get(models.Recibo, recibo_id)
    if not r:
        raise HTTPException(404, "Recibo no encontrado")
    cliente = db.get(models.Cliente, r.cliente_id)
    pagos = db.scalars(select(models.PagoCuota).where(
        models.PagoCuota.recibo_id == r.id)).all()
    pdf = recibo_pdf(r, pagos, cliente.apellido_nombre if cliente else "")
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recibo_{r.numero}.pdf"'},
    )


@router.get("/pendientes-cobro", response_model=schemas.PendientesCobro)
def pendientes_cobro(
    fecha_corte: date = Query(default_factory=date.today),
    solo_vencidas: bool = True,
    db: Session = Depends(get_db),
):
    return svc.pendientes_cobro(db, fecha_corte, solo_vencidas)


@router.get("/pendientes-cobro/pdf")
def pendientes_cobro_pdf_endpoint(
    fecha_corte: date = Query(default_factory=date.today),
    solo_vencidas: bool = True,
    db: Session = Depends(get_db),
):
    data = svc.pendientes_cobro(db, fecha_corte, solo_vencidas)
    pdf = pendientes_cobro_pdf(data)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="pendientes_{fecha_corte}.pdf"'})
