from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.cbu_agency_cache import CbuAgencyCache
from app.services import clientes_client


async def rebuild_cache(db: Session) -> int:
    agencies = await clientes_client.get_agencies()
    if not agencies:
        return 0
    # Clear and rebuild
    db.query(CbuAgencyCache).delete()
    count = 0
    for agency in agencies:
        for cbu_entry in agency.get("cbus", []):
            entry = CbuAgencyCache(
                cbu=cbu_entry["cbu"],
                client_id=agency["client_id"],
                agency_number=agency.get("agency_number"),
                legal_name=agency.get("legal_name"),
                cached_at=datetime.now(timezone.utc),
            )
            db.merge(entry)
            count += 1
    db.commit()
    return count


def lookup(db: Session, cbu: str) -> CbuAgencyCache | None:
    return db.query(CbuAgencyCache).filter(CbuAgencyCache.cbu == cbu).first()


def get_all(db: Session) -> list[CbuAgencyCache]:
    return db.query(CbuAgencyCache).all()
