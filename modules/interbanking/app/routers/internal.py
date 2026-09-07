import zlib
from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import cast
from sqlalchemy.types import Date

from app.db.session import get_db
from app.models.credentials import InterbankingCredential
from app.models.transfers import Transfer
from app.scopes import INFO_FINANCIERA
from app.services import interbanking_client, token_manager, transfer_service

router = APIRouter(tags=["internal"])


class PaymentRequest(BaseModel):
    cbu_destino: str
    monto: float
    moneda: str = "ARS"
    concepto: str = "Pago Capresca"


@router.post("/internal/interbanking/payments")
def create_payment(req: PaymentRequest, db: Session = Depends(get_db)):
    """Ejecuta un pago saliente real desde la cuenta de pagos configurada hacia
    `cbu_destino`. Lo invoca el motor de pagos de conciliación (solo cuando NO está
    en modo simulación). La idempotencia la maneja conciliación.
    """
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred or not cred.payment_account_number:
        raise HTTPException(status_code=400, detail="No hay cuenta de pagos salientes configurada")
    transfer = transfer_service.crear_transferencia(
        db=db, user_id=0,
        cuenta_debito_account_number=cred.payment_account_number,
        cuenta_debito_account_type=cred.payment_account_type or "CC",
        cuenta_debito_bank_id=cred.payment_bank_number or "011",
        cbu_destino=req.cbu_destino,
        monto=Decimal(str(req.monto)),
        moneda=req.moneda,
        comentario=req.concepto,
        username="auto-pagos",
    )
    return {"id": transfer.id, "status": transfer.status, "id_operacion_ib": transfer.id_operacion_ib}


def _norm_movement(m: dict, fallback_date: str) -> dict:
    """Normaliza un item de `movements_detail` de Interbanking al shape que consume
    el matcher de conciliación.

    Campos reales de la API (validados contra producción): el movimiento NO trae el
    CBU de la contraparte; identifica al depositante por `customer_cuit` +
    `depositor_description`. El matcheo con la agencia se resuelve por CUIT en
    conciliación. `debit_credit_type` = 'C' (crédito/depósito) | 'D' (débito).
    """
    amount = m.get("amount") or 0
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        amount = 0.0
    mid = m.get("id")
    try:
        mid_int = int(mid)
    except (TypeError, ValueError):
        mid_int = zlib.crc32(str(mid).encode()) if mid is not None else 0
    mdate = m.get("movement_date") or m.get("value_date") or m.get("process_date") or fallback_date
    concepto = m.get("code_description_ib") or m.get("code_description_bank") or m.get("depositor_description")
    return {
        "id": mid_int,
        "type": "movement",
        "date": str(mdate)[:10],
        "cbu": None,  # los movimientos no traen CBU de la contraparte
        "cuit": (str(m.get("customer_cuit") or "")).strip(),
        "depositor": m.get("depositor_description"),
        "concepto": concepto,
        "amount": amount,
        "debit_credit": m.get("debit_credit_type"),
    }


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


@router.get("/internal/interbanking/consolidation-account")
def get_consolidation_account(db: Session = Depends(get_db)):
    """Cuenta configurada como fuente de depósitos para la consolidación bancaria.
    Devuelve null si no hay ninguna elegida en la configuración de Interbanking.
    """
    from app.models.credentials import InterbankingCredential
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred or not cred.consolidation_account_number:
        return None
    return {
        "account_number": cred.consolidation_account_number,
        "account_type": cred.consolidation_account_type or "CC",
        "bank_number": cred.consolidation_bank_number or "011",
        "currency": cred.consolidation_currency or "ARS",
    }


@router.get("/internal/interbanking/payment-account")
def get_payment_account(db: Session = Depends(get_db)):
    """Cuenta de Capresca configurada como origen de los pagos salientes a agencias.
    Devuelve null si no hay ninguna elegida en la configuración de Interbanking.
    """
    from app.models.credentials import InterbankingCredential
    cred = db.query(InterbankingCredential).filter(InterbankingCredential.is_active == True).first()
    if not cred or not cred.payment_account_number:
        return None
    return {
        "account_number": cred.payment_account_number,
        "account_type": cred.payment_account_type or "CC",
        "bank_number": cred.payment_bank_number or "011",
        "currency": cred.payment_currency or "ARS",
    }


@router.get("/internal/interbanking/movements")
def get_movements(
    date: date = Query(..., description="Fecha a consolidar (yyyy-mm-dd)"),
    account_number: str = Query(..., description="Cuenta bancaria elegida como fuente de depósitos"),
    account_type: str = Query("CC", alias="account-type"),
    bank_number: str = Query("011", alias="bank-number"),
    currency: str = Query("ARS"),
    customer_id: Optional[str] = Query(None, alias="customer-id"),
    db: Session = Depends(get_db),
):
    """Movimientos (depósitos) de la cuenta elegida para un día, normalizados para
    el matcher de conciliación. Fuente real de `importe_depositado` en la
    consolidación bancaria (a diferencia de /transactions, que son transferencias).
    """
    cred = token_manager.get_active_credential(db)
    cust = customer_id or cred.customer_id
    params = {
        "customer-id": cust,
        "account-type": account_type,
        "bank-number": bank_number,
        "currency": currency,
        "date-since": date.isoformat(),
        "date-until": date.isoformat(),
        "limit": 500,
        "page": 0,
    }
    data = interbanking_client.call(
        db=db, user_id=0, operation="LISTAR_MOVIMIENTOS[conciliacion]",
        method="GET", path=f"/v1/accounts/{account_number}/movements/anteriores",
        scope=INFO_FINANCIERA, params=params,
    )
    detail = (data or {}).get("movements_detail") or []
    # Solo créditos (depósitos entrantes). Los débitos no consolidan agencia.
    return [
        _norm_movement(m, date.isoformat())
        for m in detail
        if (str(m.get("debit_credit_type") or "")).upper() == "C"
    ]
