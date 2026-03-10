import httpx
from app.config import settings


async def get_agencies() -> list[dict]:
    """Returns list of agencies with their CBUs from Clientes module."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{settings.clientes_service_url}/internal/clientes/agencies", timeout=10.0)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[clientes_client] Error fetching agencies: {e}")
        return []


async def get_agency_by_cbu(cbu: str) -> dict | None:
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{settings.clientes_service_url}/internal/clientes/cbu/{cbu}", timeout=5.0)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
    except Exception:
        return None
