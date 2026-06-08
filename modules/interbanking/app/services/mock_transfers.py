"""
Mocks para los endpoints de Transferencias Interbanking.

Activos cuando `settings.interbanking_mock_transfers` está en True (sandbox sin
credenciales `transferencias-confeccion` operativas). Replican el schema oficial
de Interbanking según la doc en `docs/Info técnica y de Infraesctructura APIS.pdf`:

  - Listado:    GET /v1/transfers/details   -> transfersDetailsGet
  - Confección: POST /v1/transfers/confection/third-party
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

# Tabla en memoria con las transferencias mockeadas (compartida entre listar y crear).
_MOCK_DB: list[dict[str, Any]] = []
_NEXT_ID = 100000


def _new_id() -> int:
    global _NEXT_ID
    _NEXT_ID += 1
    return _NEXT_ID


def _seed_if_empty() -> None:
    if _MOCK_DB:
        return
    today = date.today().isoformat()
    samples = [
        {
            "amount": "135000.00", "currency": "ARS",
            "comments": "PAGO QUINIELA 03/2026",
            "debit_account_number": "46600513539", "debit_account_type": "CC", "debit_bank_id": "011",
            "credit_cbu": "0070068930004021957614",
            "status": "ACREDITADA",
        },
        {
            "amount": "1500.50", "currency": "ARS",
            "comments": "Pago proveedor",
            "debit_account_number": "46600513539", "debit_account_type": "CC", "debit_bank_id": "011",
            "credit_cbu": "0140018920000045678904",
            "status": "PROCESANDO",
        },
        {
            "amount": "850.00", "currency": "USD",
            "comments": "Honorarios consultor",
            "debit_account_number": "46600513539", "debit_account_type": "CA", "debit_bank_id": "011",
            "credit_cbu": "0170099620000067890106",
            "status": "ACREDITADA",
        },
    ]
    for s in samples:
        _MOCK_DB.append(_build_transfer_record(
            amount=s["amount"],
            currency=s["currency"],
            comments=s["comments"],
            credit_cbu=s["credit_cbu"],
            request_date=today,
            debit_account_number=s["debit_account_number"],
            debit_account_type=s["debit_account_type"],
            debit_bank_id=s["debit_bank_id"],
            status=s["status"],
        ))


def _build_transfer_record(
    amount: str,
    currency: str,
    comments: str,
    credit_cbu: str,
    request_date: str,
    debit_account_number: str,
    debit_account_type: str = "CC",
    debit_bank_id: Optional[str] = None,
    status: str = "PENDING_AUTHORIZATION",
) -> dict[str, Any]:
    tid = _new_id()
    bank_id = debit_bank_id or "000"
    # CBU "sintético" sólo para que la grilla muestre algo cuando el sandbox no devuelve CBU
    debit_cbu_display = f"{bank_id.zfill(3)}{str(debit_account_number).zfill(19)}"[:22]
    return {
        # Schema de transfersDetailsGet (campo transfers[])
        "transfer_id": tid,
        "transaction_number": tid + 50000,
        "lot_number": 1,
        "reference_number": f"REF-{tid}",
        "request_date": request_date,
        "amount": float(amount),
        "currency": currency,
        "comments": comments,
        "credit_account": {
            "cbu": credit_cbu,
            "bank_number": credit_cbu[:3] if credit_cbu else "",
            "cuit": "30-12345678-9",
            "bank_name": "Banco Mock S.A.",
            "account_number": credit_cbu[8:] if credit_cbu else "",
            "account_type": "CC",
            "currency": currency,
        },
        "debit_account": {
            "cbu": debit_cbu_display,
            "bank_number": bank_id,
            "cuit": "30-87654321-0",
            "bank_name": "Banco Origen S.A.",
            "account_number": debit_account_number,
            "account_type": debit_account_type,
            "currency": currency,
        },
        "account_label": comments,
        "transfer_type_code": 1,
        "transfer_type_description": "MEP TR Terceros (Mock)",
        # Campo extra interno para tracking — Interbanking real no lo trae
        "_status": status,
        "_created_at": datetime.now(timezone.utc).isoformat(),
    }


def listar_transferencias(
    customer_id: str,
    date_since: Optional[str] = None,
    date_until: Optional[str] = None,
    debit_account_number: Optional[str] = None,
    credit_account_number: Optional[str] = None,
    page: int = 0,
    rows: int = 100,
) -> dict[str, Any]:
    """Imita transfersDetailsGet."""
    _seed_if_empty()

    items = list(_MOCK_DB)
    if date_since:
        items = [t for t in items if t["request_date"] >= date_since]
    if date_until:
        items = [t for t in items if t["request_date"] <= date_until]
    if debit_account_number:
        items = [t for t in items if t["debit_account"]["account_number"] == debit_account_number]
    if credit_account_number:
        items = [t for t in items if t["credit_account"]["account_number"] == credit_account_number]

    # Ordenar por fecha desc
    items.sort(key=lambda t: t["_created_at"], reverse=True)

    total = len(items)
    start = page * rows
    page_items = items[start:start + rows]

    return {
        "general_data": {
            "bank_id": "0110",
            "row_date": datetime.now(timezone.utc).isoformat(),
            "date_from": date_since,
            "date_to": date_until,
            "currency": "ARS",
            "account_number": "",
            "control_code": str(uuid4())[:8],
            "page": page,
            "limit": rows,
            "account_type": "CC",
            "total_rows": total,
        },
        "transfers": page_items,
        "_mock": True,
    }


def crear_transferencia(
    amount: str,
    currency: str,
    comments: str,
    credit_cbu: str,
    debit_account_number: str,
    debit_account_type: str = "CC",
    debit_bank_id: Optional[str] = None,
    request_date: Optional[str] = None,
    reason: Optional[str] = None,
    concept: str = "VAR",
) -> dict[str, Any]:
    """Imita POST /v1/transfers/confection/third-party (envío unificado de 1 transfer)."""
    _seed_if_empty()
    request_date = request_date or date.today().isoformat()
    confection_id = str(_new_id())

    record = _build_transfer_record(
        amount=amount,
        currency=currency,
        comments=comments,
        credit_cbu=credit_cbu,
        request_date=request_date,
        debit_account_number=debit_account_number,
        debit_account_type=debit_account_type,
        debit_bank_id=debit_bank_id,
        status="PENDING_AUTHORIZATION",
    )
    record["confection_id"] = confection_id
    record["reason"] = reason or comments
    record["concept"] = concept
    _MOCK_DB.append(record)

    return {
        "operation_id": f"OP-{confection_id}",
        "confection_id": confection_id,
        "request_date": request_date,
        "status": "PENDING_AUTHORIZATION",
        "unified_send": True,
        "found_transfers": [
            {
                "confection_id": confection_id,
                "request_date": request_date,
                "amount": amount,
                "currency": currency,
                "comments": comments,
                "debit_account": {
                    "account_number": debit_account_number,
                    "account_type": debit_account_type,
                    "bank_id": debit_bank_id,
                },
                "credit_account": {"account_cbu": credit_cbu},
                "concept": concept,
                "reason": reason or comments,
                "transfer_id": record["transfer_id"],
                "status": "PENDING_AUTHORIZATION",
            }
        ],
        "_mock": True,
    }
