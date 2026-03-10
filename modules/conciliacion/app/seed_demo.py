"""
Demo seed: carga registros de conciliación con distintos escenarios para hoy.
Ejecutar: docker compose exec conciliacion python -m app.seed_demo

Escenarios creados:
  A001 - Lotería El Dorado     → CONSOLIDADO (auto-match, neto = 0)
  A002 - Quiniela San Martín   → A_VERIFICAR (adeuda, sin depósito)
  A003 - Bingo del Centro      → CONSOLIDADO_MANUAL (pago parcial vinculado a mano)
  A004 - Lotería del Sur       → A_VERIFICAR (sin depósito, alto adeudado)
  A005 - Casino Royal          → CONSOLIDADO (auto-match, neto = 0)
  A006 - Quiniela Los Andes    → A_VERIFICAR (exceso de pago, neto negativo)
"""
import sys
from datetime import datetime, timezone, date
from decimal import Decimal
from app.db.session import SessionLocal
from app.models.reconciliation_record import ReconciliationRecord
from app.models.reconciliation_ib_link import ReconciliationIbLink
from app.models.reconciliation_status_history import ReconciliationStatusHistory
from app.models.cbu_agency_cache import CbuAgencyCache

TODAY = date.today()
NOW = datetime.now(timezone.utc)

# CBUs deben coincidir con clientes/seed_demo.py
AGENCIES = [
    {"client_id": 1, "agency_number": "A001", "legal_name": "Lotería El Dorado S.A.",      "tax_id": "30-71234567-8", "cbu": "0720099620000001234501"},
    {"client_id": 2, "agency_number": "A002", "legal_name": "Quiniela San Martín S.R.L.", "tax_id": "30-68456789-2", "cbu": "0720099620000002345602"},
    {"client_id": 3, "agency_number": "A003", "legal_name": "Bingo del Centro S.A.",       "tax_id": "30-59876543-1", "cbu": "0110012820000034567803"},
    {"client_id": 4, "agency_number": "A004", "legal_name": "Lotería del Sur S.R.L.",      "tax_id": "30-64321098-7", "cbu": "0720099620000056789005"},
    {"client_id": 5, "agency_number": "A005", "legal_name": "Casino Royal S.A.",           "tax_id": "30-77654321-9", "cbu": "0170099620000067890106"},
    {"client_id": 6, "agency_number": "A006", "legal_name": "Quiniela Los Andes S.R.L.",   "tax_id": "30-55123456-4", "cbu": "0720099620000078901207"},
]

RECORDS = [
    # id_hint, client_id, adeudado, premios, depositado, status
    # A001 → CONSOLIDADO: neto = 150000 - 15000 - 135000 = 0
    dict(client_id=1, adeudado="150000.00", premios="15000.00",  depositado="135000.00", status="CONSOLIDADO"),
    # A002 → A_VERIFICAR: neto = 89500 - 8200 - 0 = 81300
    dict(client_id=2, adeudado="89500.00",  premios="8200.00",   depositado="0.00",      status="A_VERIFICAR"),
    # A003 → CONSOLIDADO_MANUAL: neto = 320000 - 45000 - 250000 = 25000
    dict(client_id=3, adeudado="320000.00", premios="45000.00",  depositado="250000.00", status="CONSOLIDADO_MANUAL"),
    # A004 → A_VERIFICAR: neto = 185000 - 12500 - 0 = 172500
    dict(client_id=4, adeudado="185000.00", premios="12500.00",  depositado="0.00",      status="A_VERIFICAR"),
    # A005 → CONSOLIDADO: neto = 210000 - 32000 - 178000 = 0
    dict(client_id=5, adeudado="210000.00", premios="32000.00",  depositado="178000.00", status="CONSOLIDADO"),
    # A006 → A_VERIFICAR overpaid: neto = 45000 - 3000 - 50000 = -8000
    dict(client_id=6, adeudado="45000.00",  premios="3000.00",   depositado="50000.00",  status="A_VERIFICAR"),
]

# IB links ficticios (tx ids referenciando transfers insertadas por interbanking/seed_demo)
IB_LINKS = [
    # A001 transfer auto
    dict(client_id=1, tx_type="transfer", tx_id=1, amount="135000.00", cbu="0720099620000001234501", concepto="PAGO QUINIELA 03/2026", match_type="AUTO"),
    # A003 batch items manual (2 pagos parciales)
    dict(client_id=3, tx_type="batch_item", tx_id=1, amount="150000.00", cbu="0110012820000034567803", concepto="CUOTA 1 BINGO CENTRO", match_type="MANUAL"),
    dict(client_id=3, tx_type="batch_item", tx_id=2, amount="100000.00", cbu="0140018920000045678904", concepto="CUOTA 2 BINGO CENTRO", match_type="MANUAL"),
    # A005 transfer auto
    dict(client_id=5, tx_type="transfer", tx_id=2, amount="178000.00", cbu="0170099620000067890106", concepto="LIQUIDACION MARZO", match_type="AUTO"),
    # A006 transfer auto (exceso)
    dict(client_id=6, tx_type="transfer", tx_id=3, amount="50000.00", cbu="0720099620000078901207", concepto="PAGO PARCIAL QUINIELA", match_type="AUTO"),
]


def run():
    db = SessionLocal()
    try:
        # Limpiar datos demo de hoy si existen
        existing = db.query(ReconciliationRecord).filter(
            ReconciliationRecord.reconciliation_date == TODAY
        ).all()
        if existing:
            print(f"[seed_demo] Ya existen {len(existing)} registros para {TODAY}. Eliminando para re-seed.")
            for r in existing:
                db.query(ReconciliationIbLink).filter(
                    ReconciliationIbLink.reconciliation_record_id == r.id
                ).delete()
                db.query(ReconciliationStatusHistory).filter(
                    ReconciliationStatusHistory.reconciliation_record_id == r.id
                ).delete()
            db.query(ReconciliationRecord).filter(
                ReconciliationRecord.reconciliation_date == TODAY
            ).delete()
            db.flush()

        # CBU cache
        db.query(CbuAgencyCache).delete()
        for ag in AGENCIES:
            db.merge(CbuAgencyCache(
                cbu=ag["cbu"],
                client_id=ag["client_id"],
                agency_number=ag["agency_number"],
                legal_name=ag["legal_name"],
                cached_at=NOW,
            ))
        db.flush()

        # Crear registros
        record_map: dict[int, ReconciliationRecord] = {}  # client_id → record
        agency_by_cid = {ag["client_id"]: ag for ag in AGENCIES}

        for rd in RECORDS:
            ag = agency_by_cid[rd["client_id"]]
            rec = ReconciliationRecord(
                reconciliation_date=TODAY,
                client_id=rd["client_id"],
                agency_number=ag["agency_number"],
                agency_legal_name=ag["legal_name"],
                agency_tax_id=ag["tax_id"],
                importe_adeudado=Decimal(rd["adeudado"]),
                importe_premios=Decimal(rd["premios"]),
                importe_depositado=Decimal(rd["depositado"]),
                status=rd["status"],
                created_by_user_id=1,
                modified_by_user_id=1 if rd["status"] != "A_VERIFICAR" else None,
                modified_by_username="admin" if rd["status"] != "A_VERIFICAR" else None,
                modified_at=NOW if rd["status"] != "A_VERIFICAR" else None,
            )
            db.add(rec)
            db.flush()
            record_map[rd["client_id"]] = rec

            # History para los que cambiaron de estado
            if rd["status"] != "A_VERIFICAR":
                hist = ReconciliationStatusHistory(
                    reconciliation_record_id=rec.id,
                    previous_status="A_VERIFICAR",
                    new_status=rd["status"],
                    previous_importe_adeudado=Decimal(rd["adeudado"]),
                    previous_importe_premios=Decimal(rd["premios"]),
                    previous_importe_depositado=Decimal("0"),
                    new_importe_adeudado=Decimal(rd["adeudado"]),
                    new_importe_premios=Decimal(rd["premios"]),
                    new_importe_depositado=Decimal(rd["depositado"]),
                    changed_by_user_id=1,
                    changed_by_username="admin",
                    notes="Conciliación confirmada",
                )
                db.add(hist)

        db.flush()

        # Crear IB links
        for lnk in IB_LINKS:
            rec = record_map.get(lnk["client_id"])
            if not rec:
                continue
            link = ReconciliationIbLink(
                reconciliation_record_id=rec.id,
                ib_transaction_type=lnk["tx_type"],
                ib_transaction_id=lnk["tx_id"],
                ib_amount=Decimal(lnk["amount"]),
                ib_cbu=lnk["cbu"],
                ib_concepto=lnk["concepto"],
                match_type=lnk["match_type"],
                linked_by_user_id=1,
                linked_at=NOW,
            )
            db.add(link)

        db.commit()
        print(f"[seed_demo] {len(RECORDS)} registros demo cargados para {TODAY}.")
        print(f"  A001 Lotería El Dorado     → CONSOLIDADO    (neto $0)")
        print(f"  A002 Quiniela San Martín   → A_VERIFICAR    (neto $81.300)")
        print(f"  A003 Bingo del Centro      → CONSOL. MANUAL (neto $25.000)")
        print(f"  A004 Lotería del Sur       → A_VERIFICAR    (neto $172.500)")
        print(f"  A005 Casino Royal          → CONSOLIDADO    (neto $0)")
        print(f"  A006 Quiniela Los Andes    → A_VERIFICAR    (neto -$8.000 overpaid)")
    except Exception as e:
        db.rollback()
        print(f"[seed_demo] Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run()
