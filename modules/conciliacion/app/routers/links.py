from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.dependencies.auth import get_current_user_id
from app.services.link_service import delete_link_by_id

router = APIRouter(tags=["links"])


@router.delete("/links/{link_id}")
def unlink(
    link_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    record = delete_link_by_id(db, link_id, user_id)
    from app.routers.conciliacion import _record_to_dict
    return {"record": _record_to_dict(record) if record else None}
