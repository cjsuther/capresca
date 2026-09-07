"""
Motor de pagos salientes: por cada agencia con saldo a favor (saldo = depositado +
premios − adeudado > 0, es decir neto < 0), genera una transferencia desde la cuenta
de Capresca hacia la cuenta de cobro de la agencia.

Salvaguardas:
  - auto_payments_enabled=false  -> no hace nada (kill-switch).
  - payments_dry_run=true        -> registra la intención (status DRY_RUN) SIN llamar
                                    al banco. Ideal para validar antes de mover fondos.
  - Idempotencia: un pago ENVIADO por registro de conciliación; nunca paga dos veces.
"""
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.reconciliation_record import ReconciliationRecord
from app.models.reconciliation_payment import ReconciliationPayment
from app.services import clientes_client, interbanking_client

logger = logging.getLogger("conciliacion.payments")


async def _payout_cbu_map() -> dict[int, str]:
    """client_id -> CBU de cobro (el marcado is_payment_account, o el primero activo)."""
    agencies = await clientes_client.get_agencies()
    out: dict[int, str] = {}
    for ag in agencies:
        cbus = ag.get("cbus") or []
        elegido = next((c for c in cbus if c.get("is_payment_account")), None) or (cbus[0] if cbus else None)
        if elegido and elegido.get("cbu"):
            out[ag["client_id"]] = elegido["cbu"]
    return out


def _upsert_payment(db: Session, record: ReconciliationRecord, **fields) -> ReconciliationPayment:
    pay = db.query(ReconciliationPayment).filter(
        ReconciliationPayment.reconciliation_record_id == record.id
    ).first()
    if pay is None:
        pay = ReconciliationPayment(reconciliation_record_id=record.id)
        db.add(pay)
    for k, v in fields.items():
        setattr(pay, k, v)
    return pay


async def run_payments(db: Session, rec_date: date) -> dict:
    if not settings.auto_payments_enabled:
        return {"enabled": False}

    payout = await _payout_cbu_map()
    records = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.reconciliation_date == rec_date
    ).all()

    enviados = simulados = sin_cbu = errores = 0
    for r in records:
        neto = (r.importe_adeudado or Decimal("0")) - (r.importe_premios or Decimal("0")) - (r.importe_depositado or Decimal("0"))
        saldo = -neto  # positivo = hay que pagarle a la agencia
        if saldo <= 0:
            continue

        # Idempotencia: si ya hay un pago ENVIADO, no repetir
        existente = db.query(ReconciliationPayment).filter(
            ReconciliationPayment.reconciliation_record_id == r.id
        ).first()
        if existente and existente.status == "ENVIADO":
            continue

        cbu = payout.get(r.client_id)
        if not cbu:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=None, status="SIN_CBU",
                            error_message="La agencia no tiene cuenta de cobro (CBU) definida")
            sin_cbu += 1
            continue

        if settings.payments_dry_run:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=cbu, status="DRY_RUN",
                            ib_transfer_id=None, error_message=None)
            if r.status == "A_VERIFICAR":
                r.status = "A_PAGAR"
            simulados += 1
            continue

        try:
            resp = await interbanking_client.create_payment(cbu, float(saldo), settings.payment_concepto)
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=cbu, status="ENVIADO",
                            ib_transfer_id=resp.get("id"), error_message=None)
            r.status = "PAGADO"
            enviados += 1
        except Exception as e:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=cbu, status="ERROR",
                            error_message=str(e)[:500])
            errores += 1

    db.commit()
    resultado = {"enabled": True, "dry_run": settings.payments_dry_run,
                 "enviados": enviados, "simulados": simulados, "sin_cbu": sin_cbu, "errores": errores}
    logger.info("Pagos %s: %s", rec_date, resultado)
    return resultado
