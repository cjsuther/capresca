from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.reconciliation_ib_link import ReconciliationIbLink
from app.models.reconciliation_record import ReconciliationRecord


def recalculate_depositado(db: Session, record: ReconciliationRecord) -> Decimal:
    total = db.query(ReconciliationIbLink).filter(
        ReconciliationIbLink.reconciliation_record_id == record.id,
        ReconciliationIbLink.unlinked_at == None,
    ).all()
    amount = sum(lnk.ib_amount for lnk in total) if total else Decimal("0")
    record.importe_depositado = amount
    db.flush()
    return amount


def get_active_link_for_tx(db: Session, tx_type: str, tx_id: int) -> ReconciliationIbLink | None:
    return db.query(ReconciliationIbLink).filter(
        ReconciliationIbLink.ib_transaction_type == tx_type,
        ReconciliationIbLink.ib_transaction_id == tx_id,
        ReconciliationIbLink.unlinked_at == None,
    ).first()


def soft_delete_link(db: Session, link: ReconciliationIbLink, user_id: int) -> ReconciliationRecord:
    link.unlinked_at = datetime.now(timezone.utc)
    link.unlinked_by_user_id = user_id
    db.flush()
    record = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.id == link.reconciliation_record_id
    ).first()
    if record:
        recalculate_depositado(db, record)
    return record


def delete_link_by_id(db: Session, link_id: int, user_id: int):
    link = db.query(ReconciliationIbLink).filter(ReconciliationIbLink.id == link_id).first()
    if not link:
        raise HTTPException(404, "Link no encontrado")
    if link.unlinked_at:
        raise HTTPException(400, "El link ya está desvinculado")
    record = soft_delete_link(db, link, user_id)
    db.commit()
    return record
