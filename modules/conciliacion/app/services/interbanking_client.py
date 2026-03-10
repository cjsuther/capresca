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
