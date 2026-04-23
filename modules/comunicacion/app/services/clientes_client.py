import httpx
from app.config import settings


async def get_client_by_phone(phone: str) -> dict | None:
    """Busca un cliente por numero de telefono en el modulo Clientes."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.clientes_service_url}/internal/clientes/by-phone/{phone}",
                timeout=5.0,
            )
            if r.status_code == 200:
                data = r.json()
                return data if data else None
            return None
    except Exception as e:
        print(f"[clientes_client] Error fetching client by phone {phone}: {e}")
        return None


async def get_client_by_id(client_id: int) -> dict | None:
    """Obtiene datos basicos de un cliente por ID."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.clientes_service_url}/internal/clientes/{client_id}",
                timeout=5.0,
            )
            if r.status_code == 200:
                return r.json()
            return None
    except Exception as e:
        print(f"[clientes_client] Error fetching client {client_id}: {e}")
        return None


async def get_client_phones(client_id: int) -> list[dict]:
    """Obtiene los telefonos disponibles de un cliente."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{settings.clientes_service_url}/internal/clientes/{client_id}/phones",
                timeout=5.0,
            )
            if r.status_code == 200:
                return r.json()
            return []
    except Exception as e:
        print(f"[clientes_client] Error fetching phones for client {client_id}: {e}")
        return []
