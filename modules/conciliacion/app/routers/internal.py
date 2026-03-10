from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services import cbu_cache_service

router = APIRouter(tags=["internal"])


@router.post("/internal/conciliacion/refresh-cbu-cache")
async def refresh_cbu_cache(db: Session = Depends(get_db)):
    count = await cbu_cache_service.rebuild_cache(db)
    return {"refreshed": count}
