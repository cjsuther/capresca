import httpx
from app.config import settings


async def get_transactions(date_str: str) -> list[dict]:
    """Returns normalized IB transactions for a given date."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.interbanking_service_url}/internal/interbanking/transactions",
                params={"date": date_str},
                timeout=15.0,
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[interbanking_client] Error fetching transactions for {date_str}: {e}")
        return []


async def get_consolidation_account() -> dict | None:
    """Cuenta configurada en Interbanking como fuente de depósitos para consolidar."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.interbanking_service_url}/internal/interbanking/consolidation-account",
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[interbanking_client] Error fetching consolidation account: {e}")
        return None


async def get_payment_account() -> dict | None:
    """Cuenta de Capresca configurada como origen de pagos salientes."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.interbanking_service_url}/internal/interbanking/payment-account",
                timeout=10.0,
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[interbanking_client] Error fetching payment account: {e}")
        return None


async def create_payment(cbu_destino: str, monto: float, concepto: str) -> dict:
    """Ejecuta un pago saliente real (transferencia) hacia la agencia. Puede lanzar."""
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{settings.interbanking_service_url}/internal/interbanking/payments",
            json={"cbu_destino": cbu_destino, "monto": monto, "concepto": concepto},
            timeout=30.0,
        )
        r.raise_for_status()
        return r.json()


async def get_movements(date_str: str, account: dict) -> list[dict]:
    """Depósitos de la cuenta bancaria elegida para la fecha (fuente de la
    consolidación bancaria). `account` = {account_number, account-type, bank-number, currency}.
    """
    if not account or not account.get("account_number"):
        return []
    params = {
        "date": date_str,
        "account_number": account["account_number"],
        "account-type": account.get("account_type", "CC"),
        "bank-number": account.get("bank_number", "011"),
        "currency": account.get("currency", "ARS"),
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.interbanking_service_url}/internal/interbanking/movements",
                params=params,
                timeout=60.0,
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[interbanking_client] Error fetching movements for {date_str} acct={account.get('account_number')}: {e}")
        return []
