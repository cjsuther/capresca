from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import cast
from sqlalchemy.types import Date

from app.db.session import get_db
from app.models.transfers import Transfer

router = APIRouter(tags=["internal"])


@router.get("/internal/interbanking/transactions")
def get_transactions(
    date: date = Query(...),
    db: Session = Depends(get_db),
):
    transfers = db.query(Transfer).filter(
        cast(Transfer.initiated_at, Date) == date
    ).all()
    return [
        {
            "id": t.id,
            "type": "transfer",
            "date": str(date),
            "cbu": t.cbu_destino,
            "concepto": t.concepto,
            "amount": float(t.monto) if t.monto is not None else 0.0,
            "status_ib": t.status,
            "id_operacion_ib": t.id_operacion_ib,
        }
        for t in transfers
    ]
