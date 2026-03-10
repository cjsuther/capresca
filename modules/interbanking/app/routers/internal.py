from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.transfers import Transfer
from app.models.payment_batches import PaymentBatchItem, PaymentBatch
from sqlalchemy import func, cast
from sqlalchemy.types import Date

router = APIRouter(tags=["internal"])


@router.get("/internal/interbanking/transactions")
def get_transactions(
    date: date = Query(...),
    db: Session = Depends(get_db),
):
    results = []

    # Transfers: filter by initiated_at date
    transfers = db.query(Transfer).filter(
        cast(Transfer.initiated_at, Date) == date
    ).all()
    for t in transfers:
        results.append({
            "id": t.id,
            "type": "transfer",
            "date": str(date),
            "cbu": t.cbu_destino,
            "concepto": t.concepto,
            "amount": float(t.monto) if t.monto is not None else 0.0,
            "status_ib": t.status,
            "id_operacion_ib": t.id_operacion_ib,
        })

    # Payment batch items: join through batch, filter by batch.created_at date
    items = (
        db.query(PaymentBatchItem)
        .join(PaymentBatch, PaymentBatch.id == PaymentBatchItem.batch_id)
        .filter(cast(PaymentBatch.created_at, Date) == date)
        .all()
    )
    for item in items:
        results.append({
            "id": item.id,
            "type": "batch_item",
            "date": str(date),
            "cbu": item.cbu,
            "concepto": item.detalle,
            "amount": float(item.monto) if item.monto is not None else 0.0,
            "status_ib": item.status_item,
            "id_operacion_ib": None,
        })

    return results
