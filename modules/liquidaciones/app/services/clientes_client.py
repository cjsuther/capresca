import httpx
from app.config import settings


def get_registered_agency_numbers() -> set[str]:
    """Fetch all registered agency numbers from the clientes module."""
    with httpx.Client() as client:
        response = client.get(
            f"{settings.clientes_service_url}/internal/clientes/agencies",
            timeout=15.0,
        )
        response.raise_for_status()
        agencies = response.json()
        return {ag["agency_number"] for ag in agencies if ag.get("agency_number")}
