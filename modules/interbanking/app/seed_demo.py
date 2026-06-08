"""
Demo seed: crea transferencias para la fecha de hoy.
Ejecutar: docker compose exec interbanking python -m app.seed_demo
"""
import sys
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.models.transfers import Transfer

TODAY = datetime.now(timezone.utc)

TRANSFERS = [
    # A001 - Lotería El Dorado: pago exacto (CONSOLIDADO)
    {"cbu_destino": "0720099620000001234501", "monto": "135000.00", "moneda": "ARS",
     "concepto": "PAGO QUINIELA 03/2026", "status": "ACREDITADA"},
    # A005 - Casino Royal: pago exacto (CONSOLIDADO)
    {"cbu_destino": "0170099620000067890106", "monto": "178000.00", "moneda": "ARS",
     "concepto": "LIQUIDACION MARZO", "status": "ACREDITADA"},
    # A006 - Quiniela Los Andes: pago (quedan en A_VERIFICAR)
    {"cbu_destino": "0720099620000078901207", "monto": "50000.00", "moneda": "ARS",
     "concepto": "PAGO PARCIAL QUINIELA", "status": "ACREDITADA"},
    # CBU sin agencia registrada
    {"cbu_destino": "0720099620000099999999", "monto": "28500.00", "moneda": "ARS",
     "concepto": "TRANSFERENCIA SIN ASIGNAR", "status": "ACREDITADA"},
]


def run():
    db = SessionLocal()
    try:
        for t in TRANSFERS:
            db.add(Transfer(
                cbu_destino=t["cbu_destino"],
                monto=t["monto"],
                moneda=t["moneda"],
                concepto=t["concepto"],
                status=t["status"],
                initiated_by=1,
                initiated_at=TODAY,
            ))
        db.commit()
        print(f"[seed_demo] {len(TRANSFERS)} transferencias cargadas.")
    except Exception as e:
        db.rollback()
        print(f"[seed_demo] Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run()
