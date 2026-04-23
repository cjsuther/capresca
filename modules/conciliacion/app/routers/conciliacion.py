from datetime import date
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id, get_current_username
from app.services import matching_service, reconciliation_service
from app.schemas.reconciliation import (
    RecordResponse, RecordUpdate, AssignAgencyRequest, SummaryResponse
)
from app.schemas.ib_transaction import IbTransactionResponse
from app.models.reconciliation_record import ReconciliationRecord
from app.models.reconciliation_status_history import ReconciliationStatusHistory
from app.models.liquidacion_record import LiquidacionConciliacionRecord
from app.services import interbanking_client

router = APIRouter(tags=["conciliacion"])


@router.get("")
async def get_conciliacion(
    date: date = Query(...),
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    records, transactions = await matching_service.load_date(db, date)

    # Find which records have liquidacion data linked
    liq_records = db.query(LiquidacionConciliacionRecord).filter(
        LiquidacionConciliacionRecord.operation_date == date
    ).all()
    liq_record_ids = {liq.reconciliation_record_id for liq in liq_records if liq.reconciliation_record_id}

    return {
        "reconciliation_records": [_record_to_dict(r, r.id in liq_record_ids) for r in records],
        "interbanking_transactions": transactions,
    }


@router.get("/agencies")
async def list_agencies():
    from app.services import clientes_client
    return await clientes_client.get_agencies()


@router.get("/summary")
async def get_summary(
    date: date = Query(...),
    db: Session = Depends(get_db),
):
    from decimal import Decimal
    records = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.reconciliation_date == date
    ).all()
    summary = {
        "date": str(date),
        "A_VERIFICAR": sum(1 for r in records if r.status == "A_VERIFICAR"),
        "CONSOLIDADO": sum(1 for r in records if r.status == "CONSOLIDADO"),
        "CONSOLIDADO_MANUAL": sum(1 for r in records if r.status == "CONSOLIDADO_MANUAL"),
        "total_records": len(records),
        "total_importe_adeudado": sum((r.importe_adeudado or Decimal(0)) for r in records),
        "total_importe_depositado": sum((r.importe_depositado or Decimal(0)) for r in records),
        "total_importe_neto": sum(r.importe_neto for r in records),
    }
    return summary


@router.get("/records/{record_id}", response_model=RecordResponse)
def get_record(record_id: int, db: Session = Depends(get_db)):
    return _record_to_dict(reconciliation_service.get_record(db, record_id))


@router.get("/records/{record_id}/history")
def get_history(record_id: int, db: Session = Depends(get_db)):
    record = reconciliation_service.get_record(db, record_id)
    return record.history


@router.put("/records/{record_id}", response_model=RecordResponse)
async def update_record(
    record_id: int,
    data: RecordUpdate,
    user_id: int = Depends(get_current_user_id),
    username: Optional[str] = Depends(get_current_username),
    db: Session = Depends(get_db),
):
    record = reconciliation_service.get_record(db, record_id)
    # Build IB transactions map if links to add
    ib_tx_map = {}
    if data.ib_links_to_add:
        from app.models.reconciliation_ib_link import ReconciliationIbLink
        date_str = str(record.reconciliation_date)
        ib_txs = await interbanking_client.get_transactions(date_str)
        for tx in ib_txs:
            ib_tx_map[(tx["type"], tx["id"])] = tx
    updated = reconciliation_service.update_record(db, record_id, data, user_id, username, ib_tx_map)
    return _record_to_dict(updated)


@router.put("/interbanking/{tx_type}/{tx_id}/agency")
async def assign_agency(
    tx_type: str,
    tx_id: int,
    body: AssignAgencyRequest,
    user_id: int = Depends(get_current_user_id),
    username: Optional[str] = Depends(get_current_username),
    db: Session = Depends(get_db),
):
    # Need to know the date: look it up from an existing link or use today
    from datetime import date as date_type
    from app.models.reconciliation_ib_link import ReconciliationIbLink
    existing = db.query(ReconciliationIbLink).filter(
        ReconciliationIbLink.ib_transaction_type == tx_type,
        ReconciliationIbLink.ib_transaction_id == tx_id,
    ).first()
    if existing:
        rec = reconciliation_service.get_record(db, existing.reconciliation_record_id)
        rec_date = rec.reconciliation_date
    else:
        rec_date = date_type.today()

    ib_txs = await interbanking_client.get_transactions(str(rec_date))
    new_record, prev_record = await matching_service.assign_agency(
        db, tx_type, tx_id, body.client_id, user_id, username, rec_date, ib_txs
    )
    result = {"new_record": _record_to_dict(new_record)}
    if prev_record:
        result["previous_record"] = _record_to_dict(prev_record)
    return result


def _record_to_dict(r: ReconciliationRecord, has_liquidacion: bool = False) -> dict:
    from decimal import Decimal
    return {
        "id": r.id,
        "reconciliation_date": str(r.reconciliation_date),
        "client_id": r.client_id,
        "agency_number": r.agency_number,
        "agency_legal_name": r.agency_legal_name,
        "agency_tax_id": r.agency_tax_id,
        "importe_adeudado": float(r.importe_adeudado or 0),
        "importe_premios": float(r.importe_premios or 0),
        "importe_depositado": float(r.importe_depositado or 0),
        "importe_neto": float(r.importe_neto),
        "status": r.status,
        "has_liquidacion": has_liquidacion,
        "modified_by_user_id": r.modified_by_user_id,
        "modified_by_username": r.modified_by_username,
        "modified_at": r.modified_at.isoformat() if r.modified_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "links": [
            {
                "id": lnk.id,
                "ib_transaction_type": lnk.ib_transaction_type,
                "ib_transaction_id": lnk.ib_transaction_id,
                "ib_amount": float(lnk.ib_amount or 0),
                "ib_cbu": lnk.ib_cbu,
                "ib_concepto": lnk.ib_concepto,
                "match_type": lnk.match_type,
            }
            for lnk in r.links
        ] if hasattr(r, 'links') else [],
    }
