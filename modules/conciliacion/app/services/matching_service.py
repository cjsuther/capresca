from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.reconciliation_record import ReconciliationRecord
from app.models.reconciliation_ib_link import ReconciliationIbLink
from app.services import cbu_cache_service
from app.services.link_service import get_active_link_for_tx, recalculate_depositado
from app.services.reconciliation_service import get_or_create_record
from app.services import clientes_client, interbanking_client


async def load_date(db: Session, rec_date: date) -> tuple[list[ReconciliationRecord], list[dict]]:
    """
    Main orchestration:
    1. Rebuild CBU cache
    2. Get IB transactions for date
    3. Auto-match by CBU
    4. Ensure records for all agencies
    5. Sync AUTO links
    6. Recalculate importe_depositado
    Returns (records, enriched_transactions)
    """
    date_str = rec_date.isoformat()

    # Step 1: Rebuild cache
    agencies = await clientes_client.get_agencies()
    db.query(cbu_cache_service.CbuAgencyCache if False else __import__('app.models.cbu_agency_cache', fromlist=['CbuAgencyCache']).CbuAgencyCache).delete()
    from app.models.cbu_agency_cache import CbuAgencyCache
    db.query(CbuAgencyCache).delete()
    for agency in agencies:
        for cbu_entry in agency.get("cbus", []):
            entry = CbuAgencyCache(
                cbu=cbu_entry["cbu"],
                client_id=agency["client_id"],
                agency_number=agency.get("agency_number"),
                legal_name=agency.get("legal_name"),
                cached_at=datetime.now(timezone.utc),
            )
            db.merge(entry)
    db.flush()

    # Step 2: Get IB transactions
    ib_txs = await interbanking_client.get_transactions(date_str)

    # Step 3 & 4: Match and ensure records
    agency_map = {e.cbu: e for e in db.query(CbuAgencyCache).all()}
    agency_info_by_id: dict[int, dict] = {}
    for entry in agency_map.values():
        if entry.client_id not in agency_info_by_id:
            agency_info_by_id[entry.client_id] = {
                "client_id": entry.client_id,
                "agency_number": entry.agency_number,
                "legal_name": entry.legal_name or "",
                "tax_id": None,
            }

    # Ensure records for all agencies in cache
    for ag in agencies:
        get_or_create_record(db, rec_date, ag["client_id"], {
            "agency_number": ag.get("agency_number"),
            "legal_name": ag.get("legal_name", ""),
            "tax_id": ag.get("tax_id"),
        }, created_by=0)

    db.flush()

    # Step 5: Enrich transactions and sync AUTO links
    enriched = []
    for tx in ib_txs:
        cbu = tx.get("cbu")
        cache_entry = agency_map.get(cbu) if cbu else None
        tx_type = tx.get("type")
        tx_id = tx.get("id")

        resolved_client_id = None
        resolved_agency_number = None
        resolved_legal_name = None
        match_type = None
        rec_record_id = None
        rec_link_id = None

        if cache_entry:
            resolved_client_id = cache_entry.client_id
            resolved_agency_number = cache_entry.agency_number
            resolved_legal_name = cache_entry.legal_name
            # Find or create record
            record = db.query(ReconciliationRecord).filter(
                ReconciliationRecord.reconciliation_date == rec_date,
                ReconciliationRecord.client_id == cache_entry.client_id,
            ).first()
            if record:
                rec_record_id = record.id
                # Check existing link
                existing_link = get_active_link_for_tx(db, tx_type, tx_id)
                if existing_link:
                    match_type = existing_link.match_type
                    rec_link_id = existing_link.id
                    if existing_link.reconciliation_record_id != record.id:
                        # CBU re-assigned: soft-delete old, create new
                        existing_link.unlinked_at = datetime.now(timezone.utc)
                        existing_link.unlinked_by_user_id = 0
                        db.flush()
                        old_record = db.query(ReconciliationRecord).filter(
                            ReconciliationRecord.id == existing_link.reconciliation_record_id
                        ).first()
                        if old_record:
                            recalculate_depositado(db, old_record)
                        new_link = ReconciliationIbLink(
                            reconciliation_record_id=record.id,
                            ib_transaction_type=tx_type,
                            ib_transaction_id=tx_id,
                            ib_amount=Decimal(str(tx.get("amount", 0))),
                            ib_cbu=cbu or "",
                            ib_concepto=tx.get("concepto"),
                            match_type="AUTO",
                            linked_by_user_id=0,
                        )
                        db.add(new_link)
                        db.flush()
                        match_type = "AUTO"
                        rec_link_id = new_link.id
                else:
                    # Create AUTO link
                    new_link = ReconciliationIbLink(
                        reconciliation_record_id=record.id,
                        ib_transaction_type=tx_type,
                        ib_transaction_id=tx_id,
                        ib_amount=Decimal(str(tx.get("amount", 0))),
                        ib_cbu=cbu or "",
                        ib_concepto=tx.get("concepto"),
                        match_type="AUTO",
                        linked_by_user_id=0,
                    )
                    db.add(new_link)
                    db.flush()
                    match_type = "AUTO"
                    rec_link_id = new_link.id
        else:
            # Check if there's a MANUAL link already
            existing_link = get_active_link_for_tx(db, tx_type, tx_id)
            if existing_link:
                rec_record_id = existing_link.reconciliation_record_id
                match_type = existing_link.match_type
                rec_link_id = existing_link.id
                record = db.query(ReconciliationRecord).filter(
                    ReconciliationRecord.id == rec_record_id
                ).first()
                if record:
                    resolved_client_id = record.client_id
                    resolved_agency_number = record.agency_number
                    resolved_legal_name = record.agency_legal_name

        enriched.append({**tx,
            "resolved_client_id": resolved_client_id,
            "resolved_agency_number": resolved_agency_number,
            "resolved_legal_name": resolved_legal_name,
            "match_type": match_type,
            "reconciliation_record_id": rec_record_id,
            "reconciliation_link_id": rec_link_id,
        })

    # Step 6: Recalculate importe_depositado for all records of this date
    records = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.reconciliation_date == rec_date
    ).all()
    for r in records:
        recalculate_depositado(db, r)
    db.commit()

    for r in records:
        db.refresh(r)

    return records, enriched


async def assign_agency(db: Session, tx_type: str, tx_id: int, client_id: int,
                        user_id: int, username: str | None,
                        rec_date: date, ib_txs: list[dict]) -> tuple:
    """Assign or reassign a transaction to an agency."""
    from app.services.link_service import soft_delete_link

    tx = next((t for t in ib_txs if t["type"] == tx_type and t["id"] == tx_id), None)
    if not tx:
        from fastapi import HTTPException
        raise HTTPException(404, "Transacción IB no encontrada")

    # Soft-delete existing link if any
    existing_link = get_active_link_for_tx(db, tx_type, tx_id)
    prev_record = None
    if existing_link:
        prev_record = soft_delete_link(db, existing_link, user_id)

    # Determine if CBU matches agency (AUTO vs MANUAL)
    from app.models.cbu_agency_cache import CbuAgencyCache
    cbu = tx.get("cbu")
    cache_entry = db.query(CbuAgencyCache).filter(CbuAgencyCache.cbu == cbu).first() if cbu else None
    match_type = "AUTO" if (cache_entry and cache_entry.client_id == client_id) else "MANUAL"

    # Get agency info from cache
    from app.services.reconciliation_service import get_or_create_record
    agency_cache = db.query(CbuAgencyCache).filter(CbuAgencyCache.client_id == client_id).first()
    agency_info = {
        "agency_number": agency_cache.agency_number if agency_cache else None,
        "legal_name": agency_cache.legal_name if agency_cache else f"Cliente {client_id}",
        "tax_id": None,
    }
    new_record = get_or_create_record(db, rec_date, client_id, agency_info, user_id)

    new_link = ReconciliationIbLink(
        reconciliation_record_id=new_record.id,
        ib_transaction_type=tx_type,
        ib_transaction_id=tx_id,
        ib_amount=Decimal(str(tx.get("amount", 0))),
        ib_cbu=cbu or "",
        ib_concepto=tx.get("concepto"),
        match_type=match_type,
        linked_by_user_id=user_id,
    )
    db.add(new_link)
    recalculate_depositado(db, new_record)
    db.commit()
    db.refresh(new_record)

    return new_record, prev_record
