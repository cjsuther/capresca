from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.transfers import Transfer
from app.scopes import TRANSFERENCIAS_CONFECCION, INFO_FINANCIERA
from app.services import interbanking_client, mock_transfers, token_manager
from app.services.notifications_client import notifications_client


# ─────────────────────────────────────────────────────────────────────────────
# Listado local (registro propio)
# ─────────────────────────────────────────────────────────────────────────────
def list_local_transfers(db: Session, page: int = 1, per_page: int = 20):
    q = db.query(Transfer).order_by(Transfer.initiated_at.desc())
    total = q.count()
    data = q.offset((page - 1) * per_page).limit(per_page).all()
    return data, total


# ─────────────────────────────────────────────────────────────────────────────
# Crear transferencia: POST /v1/transfers/confection/third-party
# ─────────────────────────────────────────────────────────────────────────────
def _resolve_debit_cbu(db: Session, user_id: int, account_number: str, account_type: str, bank_id: Optional[str], ip: Optional[str]) -> Optional[str]:
    """Para llamada real: obtiene el CBU de la cuenta débito vía /v1/accounts/{account-number}."""
    params: dict = {"account-type": account_type}
    if bank_id:
        params["bank-number"] = bank_id
    cred = token_manager.get_active_credential(db)
    if cred.customer_id:
        params["customer-id"] = cred.customer_id
    try:
        data = interbanking_client.call(
            db=db, user_id=user_id,
            operation="RESOLVE_DEBIT_CBU",
            method="GET",
            path=f"/v1/accounts/{account_number}",
            scope=INFO_FINANCIERA,
            params=params,
            ip_address=ip,
        )
        # La API devuelve `account_cbu` y `bank_number` (verificado con la credencial productiva el
        # 2026-10-07); `cbu` / `bank_id` quedan por compatibilidad con respuestas viejas o del sandbox.
        accounts = (data or {}).get("accounts") or []
        cbu_de = lambda a: a.get("account_cbu") or a.get("cbu") or None
        banco_de = lambda a: a.get("bank_number") or a.get("bank_id")
        for a in accounts:
            if a.get("account_type") == account_type and (not bank_id or banco_de(a) == bank_id):
                return cbu_de(a)
        if accounts:
            return cbu_de(accounts[0])
    except Exception:
        return None
    return None


def _numero_operador(username: Optional[str]) -> Optional[int]:
    """El usuario del Operador de API es `-3|<número de operador>|<usuario>`."""
    partes = (username or "").split("|")
    return int(partes[1]) if len(partes) == 3 and partes[1].isdigit() else None


def _num(v: str):
    """La especificación tipa número de cuenta y banco como enteros; si no es numérico va tal cual."""
    return int(v) if str(v).isdigit() else v


# Interbanking valida la fecha de solicitud contra el día de Argentina (UTC-3, sin horario de verano);
# el contenedor corre en UTC y desde las 21 h ya sería "mañana".
_ARGENTINA = timezone(timedelta(hours=-3))

# `confection_id`: hasta 7 dígitos (400 "1007 - La longitud del campo confection_id debe ser de un
# máximo de 7"). Se usa el id del registro local de la transferencia, que es único y creciente.
_MAX_CONFECTION_ID = 10_000_000


def crear_transferencia(
    db: Session,
    user_id: int,
    cuenta_debito_account_number: str,
    cuenta_debito_account_type: str,
    cuenta_debito_bank_id: Optional[str],
    cbu_destino: str,
    monto: Decimal,
    moneda: str,
    comentario: str,
    username: Optional[str] = None,
    ip: Optional[str] = None,
) -> Transfer:
    request_date = datetime.now(_ARGENTINA).date().isoformat()
    amount_str = f"{monto:.2f}"
    cuenta_origen_label = "/".join(filter(None, [
        cuenta_debito_bank_id, cuenta_debito_account_number, cuenta_debito_account_type,
    ]))

    if settings.interbanking_mock_transfers:
        result = mock_transfers.crear_transferencia(
            amount=amount_str,
            currency=moneda,
            comments=comentario,
            credit_cbu=cbu_destino,
            debit_account_number=cuenta_debito_account_number,
            debit_account_type=cuenta_debito_account_type,
            debit_bank_id=cuenta_debito_bank_id,
            request_date=request_date,
        )
    else:
        # Interbanking real exige account_cbu del débito → lo resolvemos primero
        debit_cbu = _resolve_debit_cbu(
            db, user_id,
            cuenta_debito_account_number,
            cuenta_debito_account_type,
            cuenta_debito_bank_id,
            ip,
        )
        if not debit_cbu:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No se pudo resolver el CBU de la cuenta débito en Interbanking. "
                    "Verificá que la cuenta tenga CBU asociado."
                ),
            )
        # Cuerpo según el ejemplo de la especificación productiva (docs/trans.txt): producción exige
        # `confection_id` en cada transferencia (400 "1005 - No se informó el campo confection_id").
        cred = token_manager.get_active_credential(db)
        # El registro local se crea antes del envío: su id es el confection_id y, si Interbanking
        # rechaza el pedido, queda asentado como ERROR.
        transfer = Transfer(
            cuenta_origen=cuenta_origen_label, cbu_destino=cbu_destino, monto=monto, moneda=moneda,
            concepto=comentario, status="ENVIANDO", initiated_by=user_id,
        )
        db.add(transfer)
        db.flush()
        confection_id = transfer.id % _MAX_CONFECTION_ID
        payload = {
            "consolidated_check": False,
            "description": comentario,
            "payment_number": confection_id,
            "unified_send": True,
            "found_transfers": [
                {
                    "confection_id": confection_id,
                    # Sólo la fecha: con hora ("...T00:00:00.000Z") responde 1004 "no es una fecha válida".
                    "request_date": request_date,
                    "amount": float(amount_str),
                    "comments": comentario,
                    "debit_account": {
                        "bank_number": int(cuenta_debito_bank_id or debit_cbu[:3]),
                        "account_type": cuenta_debito_account_type,
                        "currency": moneda,
                        "account_number": _num(cuenta_debito_account_number),
                        "account_cbu": debit_cbu,
                    },
                    "credit_account": {
                        "bank_number": int(cbu_destino[:3]),
                        "currency": moneda,
                        "account_cbu": cbu_destino,
                    },
                    "concept": "VAR",
                    "disclaimer_accepted": True,
                    "reason": comentario,
                }
            ],
        }
        operador = _numero_operador(cred.username)
        if operador:
            payload["operator_id"] = operador
        db.commit()
        try:
            result = interbanking_client.call(
                db=db,
                user_id=user_id,
                operation="CREAR_TRANSFERENCIA",
                method="POST",
                path="/v1/transfers/confection/third-party",
                scope=TRANSFERENCIAS_CONFECCION,
                payload=payload,
                username=username,
                ip_address=ip,
            )
        except HTTPException as e:
            transfer.status = "ERROR"
            transfer.last_status_payload = {"confection_id": confection_id, "error": str(e.detail)}
            db.commit()
            raise

    # Persistir en tabla local
    found = (result.get("found_transfers") or [{}])[0]
    id_op = (
        result.get("operation_id")
        or result.get("confection_id")
        or found.get("confection_id")
    )
    if settings.interbanking_mock_transfers:
        transfer = Transfer(
            cuenta_origen=cuenta_origen_label, cbu_destino=cbu_destino, monto=monto, moneda=moneda,
            concepto=comentario, initiated_by=user_id,
        )
        db.add(transfer)
    transfer.id_operacion_ib = str(id_op) if id_op else None
    transfer.status = found.get("status") or result.get("status") or "INICIADA"
    transfer.last_status_payload = result
    db.commit()
    db.refresh(transfer)

    notifications_client.notify(
        user_id=user_id,
        title="Transferencia registrada",
        message=(
            f"Tu transferencia por {monto} {moneda} a {cbu_destino} quedó en "
            f"estado {transfer.status}."
        ),
        module="interbanking",
        entity_type="transfer",
        entity_id=transfer.id,
        redirect_path="/modules/interbanking/transferencias",
    )
    return transfer


# ─────────────────────────────────────────────────────────────────────────────
# Listar transferencias: GET /v1/transfers/details (info-financiera)
# Acepta filtros por fecha; default a "hoy".
# ─────────────────────────────────────────────────────────────────────────────
def listar_transferencias_remoto(
    db: Session,
    user_id: int,
    date_since: Optional[str] = None,
    date_until: Optional[str] = None,
    debit_cbu: Optional[str] = None,
    credit_cbu: Optional[str] = None,
    page: int = 0,
    rows: int = 100,
    username: Optional[str] = None,
    ip: Optional[str] = None,
) -> dict:
    today = date.today().isoformat()
    date_since = date_since or today
    date_until = date_until or today

    if settings.interbanking_mock_transfers:
        return mock_transfers.listar_transferencias(
            customer_id="MOCK",
            date_since=date_since,
            date_until=date_until,
            page=page,
            rows=rows,
        )

    cred = token_manager.get_active_credential(db)
    if not cred.customer_id:
        raise HTTPException(status_code=400, detail="customer_id no configurado")

    params: dict = {
        "customer-id": cred.customer_id,
        "date-since": date_since,
        "date-until": date_until,
        "page": page,
        # Interbanking pagina con `limit` (página desde 0) y rechaza `rows` con 400
        # "El parámetro rows no es esperado" (verificado en producción el 2026-10-09).
        "limit": rows,
    }
    if debit_cbu:
        params["debit-account-number"] = debit_cbu
    if credit_cbu:
        params["credit-account-number"] = credit_cbu

    return interbanking_client.call(
        db=db,
        user_id=user_id,
        operation="LISTAR_TRANSFERENCIAS",
        method="GET",
        path="/v1/transfers/details",
        scope=INFO_FINANCIERA,
        params=params,
        username=username,
        ip_address=ip,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints legacy de la versión anterior (mantenidos por compat)
# ─────────────────────────────────────────────────────────────────────────────
def validar_cbu(db: Session, user_id: int, cbu_or_alias: str, username: Optional[str] = None, ip: Optional[str] = None):
    if settings.interbanking_mock_transfers:
        return {
            "cbu": cbu_or_alias if len(cbu_or_alias) == 22 else "0000000000000000000000",
            "titular": "Titular MOCK",
            "banco": "Banco Mock S.A.",
            "tipo_cuenta": "CC",
            "_mock": True,
        }
    return interbanking_client.call(
        db=db, user_id=user_id, operation="VALIDAR_CBU",
        method="POST", path="/transferencias/validar",
        scope=TRANSFERENCIAS_CONFECCION,
        payload={"cbu_or_alias": cbu_or_alias},
        username=username, ip_address=ip,
    )


def get_estado_transferencia(db: Session, user_id: int, transfer_id: str, username: Optional[str] = None, ip: Optional[str] = None):
    if settings.interbanking_mock_transfers:
        return {"id_operacion": transfer_id, "status": "ACREDITADA", "_mock": True}
    result = interbanking_client.call(
        db=db, user_id=user_id, operation="ESTADO_TRANSFERENCIA",
        method="GET", path=f"/transferencias/{transfer_id}/estado",
        scope=TRANSFERENCIAS_CONFECCION,
        username=username, ip_address=ip,
    )
    transfer = db.query(Transfer).filter(Transfer.id_operacion_ib == transfer_id).first()
    if transfer:
        transfer.status = result.get("status", transfer.status)
        transfer.last_status_check = datetime.now(timezone.utc)
        transfer.last_status_payload = result
        db.commit()
    return result
