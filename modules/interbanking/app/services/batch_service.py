from datetime import datetime, timezone
from decimal import Decimal
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.payment_batches import PaymentBatch, PaymentBatchItem
from app.schemas.payment_batches import BatchCreate
from app.services import interbanking_client


def list_batches(db: Session, page: int = 1, per_page: int = 20):
    q = db.query(PaymentBatch).order_by(PaymentBatch.created_at.desc())
    total = q.count()
    data = q.offset((page - 1) * per_page).limit(per_page).all()
    return data, total


def get_batch(db: Session, batch_id: int) -> PaymentBatch:
    batch = db.query(PaymentBatch).filter(PaymentBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    return batch


def create_batch(db: Session, user_id: int, data: BatchCreate) -> PaymentBatch:
    total_amount = sum(item.monto for item in data.items)
    batch = PaymentBatch(
        descripcion=data.descripcion,
        status="BORRADOR",
        total_items=len(data.items),
        total_amount=total_amount,
        created_by=user_id,
    )
    db.add(batch)
    db.flush()
    for item in data.items:
        db.add(PaymentBatchItem(
            batch_id=batch.id,
            cbu=item.cbu,
            monto=item.monto,
            detalle=item.detalle,
        ))
    db.commit()
    db.refresh(batch)
    return batch


def procesar_batch(db: Session, batch_id: int, user_id: int, username: str = None, ip: str = None) -> PaymentBatch:
    batch = get_batch(db, batch_id)
    items_payload = [
        {"cbu": i.cbu, "monto": str(i.monto), "detalle": i.detalle}
        for i in batch.items
    ]
    result = interbanking_client.call(
        db=db,
        user_id=user_id,
        operation="PROCESAR_LOTE",
        method="POST",
        path=f"/pagos/lotes/{batch_id}/procesar",
        payload={"items": items_payload},
        username=username,
        ip_address=ip,
    )
    batch.status = result.get("status", "ENVIADO")
    batch.id_lote_ib = result.get("id_lote")
    batch.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(batch)
    return batch


def get_estado_batch(db: Session, batch_id: int, user_id: int, username: str = None, ip: str = None):
    batch = get_batch(db, batch_id)
    result = interbanking_client.call(
        db=db,
        user_id=user_id,
        operation="ESTADO_LOTE",
        method="GET",
        path=f"/pagos/lotes/{batch.id_lote_ib or batch_id}/estado",
        username=username,
        ip_address=ip,
    )
    batch.status = result.get("status", batch.status)
    batch.last_status_check = datetime.now(timezone.utc)
    batch.last_status_payload = result
    db.commit()
    db.refresh(batch)
    return batch
