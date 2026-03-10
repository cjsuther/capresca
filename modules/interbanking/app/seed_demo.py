"""
Demo seed: crea transferencias y lotes de pago para la fecha de hoy.
Ejecutar: docker compose exec interbanking python -m app.seed_demo
"""
import sys
from datetime import datetime, timezone, date
from app.db.session import SessionLocal
from app.models.transfers import Transfer
from app.models.payment_batches import PaymentBatch, PaymentBatchItem

# CBUs de las 6 agencias demo (deben coincidir con clientes seed_demo)
TODAY = datetime.now(timezone.utc)

TRANSFERS = [
    # A001 - Lotería El Dorado: pago exacto (CONSOLIDADO)
    {"cbu_destino": "0720099620000001234501", "monto": "135000.00", "concepto": "PAGO QUINIELA 03/2026", "status": "ACREDITADA"},
    # A005 - Casino Royal: pago exacto (CONSOLIDADO)
    {"cbu_destino": "0170099620000067890106", "monto": "178000.00", "concepto": "LIQUIDACION MARZO", "status": "ACREDITADA"},
    # A006 - Quiniela Los Andes: pago (quedan en A_VERIFICAR)
    {"cbu_destino": "0720099620000078901207", "monto": "50000.00", "concepto": "PAGO PARCIAL QUINIELA", "status": "ACREDITADA"},
    # CBU sin agencia registrada
    {"cbu_destino": "0720099620000099999999", "monto": "28500.00", "concepto": "TRANSFERENCIA SIN ASIGNAR", "status": "ACREDITADA"},
    # A004 - Lotería del Sur: sin pago todavía (no se crea transfer)
]

BATCH_ITEMS = [
    # A003 - Bingo del Centro: dos pagos parciales (CONSOLIDADO_MANUAL)
    {"cbu": "0110012820000034567803", "monto": "150000.00", "detalle": "CUOTA 1 BINGO CENTRO"},
    {"cbu": "0140018920000045678904", "monto": "100000.00", "detalle": "CUOTA 2 BINGO CENTRO"},
    # A002 - Quiniela San Martín: pago batch pendiente
    {"cbu": "0720099620000002345602", "monto": "45000.00", "detalle": "PAGO SAN MARTIN LOTE"},
]


def run():
    db = SessionLocal()
    try:
        # Transferencias
        for t in TRANSFERS:
            tr = Transfer(
                cbu_destino=t["cbu_destino"],
                monto=t["monto"],
                concepto=t["concepto"],
                status=t["status"],
                initiated_by=1,
                initiated_at=TODAY,
            )
            db.add(tr)

        db.flush()

        # Lote de pago con items
        batch = PaymentBatch(
            descripcion="LOTE DEMO " + date.today().strftime("%d/%m/%Y"),
            status="PROCESADO",
            total_items=len(BATCH_ITEMS),
            total_amount=sum(float(b["monto"]) for b in BATCH_ITEMS),
            created_by=1,
            created_at=TODAY,
        )
        db.add(batch)
        db.flush()

        for item_data in BATCH_ITEMS:
            item = PaymentBatchItem(
                batch_id=batch.id,
                cbu=item_data["cbu"],
                monto=item_data["monto"],
                detalle=item_data["detalle"],
                status_item="ACREDITADO",
            )
            db.add(item)

        db.commit()
        print(f"[seed_demo] {len(TRANSFERS)} transferencias y {len(BATCH_ITEMS)} items de lote cargados para {date.today()}.")
    except Exception as e:
        db.rollback()
        print(f"[seed_demo] Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run()
