from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.authorization_rule import AuthorizationRule
from app.models.transaction import Transaction


def evaluate_rules(
    db: Session,
    cajero_user_id: int,
    currency: str,
    amount: Decimal,
    reference: str | None,
) -> list[AuthorizationRule]:
    """
    Returns list of triggered rules for this transaction.
    A rule is triggered when the cumulative amount (existing non-deleted transactions
    with same scope + new amount) exceeds amount_limit.
    """
    rules = db.query(AuthorizationRule).filter(
        AuthorizationRule.cajero_user_id == cajero_user_id,
        AuthorizationRule.currency == currency,
        AuthorizationRule.is_active == True,
    ).all()

    triggered = []
    for rule in rules:
        # Determine scope of existing transactions to sum
        q = db.query(Transaction).filter(
            Transaction.cajero_user_id == cajero_user_id,
            Transaction.currency == currency,
            Transaction.status != "ELIMINADA",
        )
        if rule.reference is not None:
            # Rule applies only to transactions with same reference
            q = q.filter(Transaction.reference == rule.reference)
            # Only check if new transaction has same reference
            if reference != rule.reference:
                continue
        # Sum existing + new amount
        existing_total = sum(t.amount for t in q.all()) if q.count() > 0 else Decimal("0")
        total = existing_total + amount
        if total > rule.amount_limit:
            triggered.append(rule)

    return triggered
