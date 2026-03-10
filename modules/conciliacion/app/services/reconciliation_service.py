from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.reconciliation_record import ReconciliationRecord
from app.models.reconciliation_ib_link import ReconciliationIbLink
from app.models.reconciliation_status_history import ReconciliationStatusHistory
from app.schemas.reconciliation import RecordUpdate
from app.services.link_service import recalculate_depositado, get_active_link_for_tx, soft_delete_link


def get_record(db: Session, record_id: int) -> ReconciliationRecord:
    r = db.query(ReconciliationRecord).filter(ReconciliationRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, "Registro no encontrado")
    return r


def get_or_create_record(db: Session, rec_date: date, client_id: int, agency_info: dict, created_by: int) -> ReconciliationRecord:
    existing = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.reconciliation_date == rec_date,
        ReconciliationRecord.client_id == client_id,
    ).first()
    if existing:
        return existing
    record = ReconciliationRecord(
        reconciliation_date=rec_date,
        client_id=client_id,
        agency_number=agency_info.get("agency_number"),
        agency_legal_name=agency_info.get("legal_name", ""),
        agency_tax_id=agency_info.get("tax_id"),
        importe_adeudado=Decimal("0"),
        importe_premios=Decimal("0"),
        importe_depositado=Decimal("0"),
        status="A_VERIFICAR",
        created_by_user_id=created_by,
    )
    db.add(record)
    db.flush()
    return record


def update_record(db: Session, record_id: int, data: RecordUpdate, user_id: int, username: str | None,
                  ib_transactions_map: dict) -> ReconciliationRecord:
    record = get_record(db, record_id)

    # Snapshot before
    prev = {
        "status": record.status,
        "importe_adeudado": record.importe_adeudado,
        "importe_premios": record.importe_premios,
        "importe_depositado": record.importe_depositado,
    }

    if data.importe_adeudado is not None:
        record.importe_adeudado = data.importe_adeudado
    if data.importe_premios is not None:
        record.importe_premios = data.importe_premios
    if data.status is not None:
        record.status = data.status

    # Remove links
    for link_id in data.ib_links_to_remove:
        from app.models.reconciliation_ib_link import ReconciliationIbLink
        link = db.query(ReconciliationIbLink).filter(ReconciliationIbLink.id == link_id).first()
        if link and not link.unlinked_at:
            soft_delete_link(db, link, user_id)

    # Add links
    for item in data.ib_links_to_add:
        tx_key = (item.ib_transaction_type, item.ib_transaction_id)
        tx = ib_transactions_map.get(tx_key)
        if not tx:
            continue
        existing_link = get_active_link_for_tx(db, item.ib_transaction_type, item.ib_transaction_id)
        if existing_link:
            if existing_link.reconciliation_record_id == record.id:
                continue
            soft_delete_link(db, existing_link, user_id)
        link = ReconciliationIbLink(
            reconciliation_record_id=record.id,
            ib_transaction_type=item.ib_transaction_type,
            ib_transaction_id=item.ib_transaction_id,
            ib_amount=tx.get("amount", Decimal("0")),
            ib_cbu=tx.get("cbu", ""),
            ib_concepto=tx.get("concepto"),
            match_type="MANUAL",
            linked_by_user_id=user_id,
        )
        db.add(link)

    recalculate_depositado(db, record)
    record.modified_by_user_id = user_id
    record.modified_by_username = username
    record.modified_at = datetime.now(timezone.utc)

    # History entry
    history = ReconciliationStatusHistory(
        reconciliation_record_id=record.id,
        previous_status=prev["status"],
        new_status=record.status,
        previous_importe_adeudado=prev["importe_adeudado"],
        previous_importe_premios=prev["importe_premios"],
        previous_importe_depositado=prev["importe_depositado"],
        new_importe_adeudado=record.importe_adeudado,
        new_importe_premios=record.importe_premios,
        new_importe_depositado=record.importe_depositado,
        changed_by_user_id=user_id,
        changed_by_username=username,
        notes=data.notes,
    )
    db.add(history)
    db.commit()
    db.refresh(record)
    return record
