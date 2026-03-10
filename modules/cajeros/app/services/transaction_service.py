from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.transaction import Transaction, TransactionRuleTrigger
from app.models.authorization_rule import AuthorizationRule
from app.schemas.transactions import TransactionCreate, RejectTransaction
from app.services.rule_evaluator import evaluate_rules
from app.services.notifications_client import notifications_client


async def create_transaction(
    db: Session,
    data: TransactionCreate,
    cajero_user_id: int,
    cajero_username: str | None = None,
) -> Transaction:
    triggered_rules = evaluate_rules(db, cajero_user_id, data.currency, data.amount, data.reference)

    # Determine status and primary authorizer
    if triggered_rules:
        status = "PENDIENTE_AUTORIZACION"
        # Use authorizer from the first triggered rule as the primary
        authorizer_user_id = triggered_rules[0].authorizer_user_id
        authorizer_username = triggered_rules[0].authorizer_username
    else:
        status = "PROCESADA"
        authorizer_user_id = None
        authorizer_username = None

    tx = Transaction(
        cajero_user_id=cajero_user_id,
        cajero_username=cajero_username,
        authorizer_user_id=authorizer_user_id,
        authorizer_username=authorizer_username,
        currency=data.currency,
        amount=data.amount,
        reference=data.reference,
        description=data.description,
        status=status,
        created_by=cajero_user_id,
    )
    db.add(tx)
    db.flush()

    # Create trigger records
    for rule in triggered_rules:
        trigger = TransactionRuleTrigger(
            transaction_id=tx.id,
            rule_id=rule.id,
            authorizer_user_id=rule.authorizer_user_id,
        )
        db.add(trigger)

    db.commit()
    db.refresh(tx)

    # Send notifications to all triggered authorizers (fire-and-forget)
    if triggered_rules:
        unique_authorizers = {r.authorizer_user_id: r.authorizer_username for r in triggered_rules}
        notifs = [
            {
                "user_id": auth_id,
                "title": "Transacción pendiente de autorización",
                "message": f"Nueva transacción de {cajero_username or cajero_user_id} por {data.amount} {data.currency}",
                "module": "cajeros",
                "entity_type": "transaction",
                "entity_id": tx.id,
                "redirect_path": f"/modules/cajeros/transactions/{tx.id}",
                "created_by_module": "cajeros",
            }
            for auth_id in unique_authorizers
        ]
        await notifications_client.notify_many(notifs)

    return tx


def get_transactions(
    db: Session,
    user_id: int,
    can_read_all: bool = False,
    status_filter: list[str] | None = None,
    currency: str | None = None,
    cajero_filter: int | None = None,
    date_from=None,
    date_to=None,
) -> list[Transaction]:
    q = db.query(Transaction)
    if not can_read_all:
        from sqlalchemy import or_
        q = q.filter(
            or_(Transaction.cajero_user_id == user_id, Transaction.authorizer_user_id == user_id)
        )
    if status_filter:
        q = q.filter(Transaction.status.in_(status_filter))
    if currency:
        q = q.filter(Transaction.currency == currency)
    if cajero_filter:
        q = q.filter(Transaction.cajero_user_id == cajero_filter)
    if date_from:
        q = q.filter(Transaction.created_at >= date_from)
    if date_to:
        q = q.filter(Transaction.created_at <= date_to)

    # PENDIENTE_AUTORIZACION first, then updated_at DESC
    from sqlalchemy import case
    priority = case({"PENDIENTE_AUTORIZACION": 0}, value=Transaction.status, else_=1)
    return q.order_by(priority, Transaction.updated_at.desc()).all()


def get_transaction(db: Session, transaction_id: int) -> Transaction:
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transacción no encontrada")
    return tx


async def authorize_transaction(
    db: Session,
    transaction_id: int,
    authorizer_user_id: int,
    authorizer_username: str | None = None,
) -> Transaction:
    tx = get_transaction(db, transaction_id)
    if tx.status != "PENDIENTE_AUTORIZACION":
        raise HTTPException(status_code=400, detail="Solo se pueden autorizar transacciones PENDIENTE_AUTORIZACION")
    if tx.authorizer_user_id and tx.authorizer_user_id != authorizer_user_id:
        raise HTTPException(status_code=403, detail="No está asignado como autorizador de esta transacción")

    tx.status = "AUTORIZADA"
    tx.authorized_at = datetime.now(timezone.utc)
    tx.updated_at = datetime.now(timezone.utc)
    tx.authorizer_user_id = authorizer_user_id
    tx.authorizer_username = authorizer_username
    db.commit()
    db.refresh(tx)

    # Notify cajero
    await notifications_client.notify(
        user_id=tx.cajero_user_id,
        title="Transacción autorizada",
        message=f"Tu transacción #{tx.id} por {tx.amount} {tx.currency} fue autorizada por {authorizer_username or authorizer_user_id}",
        module="cajeros",
        entity_type="transaction",
        entity_id=tx.id,
        redirect_path=f"/modules/cajeros/transactions/{tx.id}",
    )
    return tx


async def reject_transaction(
    db: Session,
    transaction_id: int,
    authorizer_user_id: int,
    authorizer_username: str | None = None,
    data: RejectTransaction = None,
) -> Transaction:
    tx = get_transaction(db, transaction_id)
    if tx.status != "PENDIENTE_AUTORIZACION":
        raise HTTPException(status_code=400, detail="Solo se pueden rechazar transacciones PENDIENTE_AUTORIZACION")
    if tx.authorizer_user_id and tx.authorizer_user_id != authorizer_user_id:
        raise HTTPException(status_code=403, detail="No está asignado como autorizador de esta transacción")

    tx.status = "RECHAZADA"
    tx.authorized_at = datetime.now(timezone.utc)
    tx.updated_at = datetime.now(timezone.utc)
    tx.authorizer_user_id = authorizer_user_id
    tx.authorizer_username = authorizer_username
    tx.rejection_reason = data.rejection_reason if data else None
    db.commit()
    db.refresh(tx)

    # Notify cajero
    await notifications_client.notify(
        user_id=tx.cajero_user_id,
        title="Transacción rechazada",
        message=f"Tu transacción #{tx.id} fue rechazada por {authorizer_username or authorizer_user_id}: {tx.rejection_reason}",
        module="cajeros",
        entity_type="transaction",
        entity_id=tx.id,
        redirect_path=f"/modules/cajeros/transactions/{tx.id}",
    )
    return tx


def delete_transaction(db: Session, transaction_id: int, user_id: int, is_admin: bool = False) -> Transaction:
    tx = get_transaction(db, transaction_id)
    if tx.status != "PENDIENTE_AUTORIZACION":
        raise HTTPException(status_code=400, detail="Solo se pueden eliminar transacciones PENDIENTE_AUTORIZACION")
    if not is_admin and tx.cajero_user_id != user_id:
        raise HTTPException(status_code=403, detail="Solo el cajero dueño o un admin puede eliminar esta transacción")
    tx.status = "ELIMINADA"
    tx.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tx)
    return tx
