"""Utilidades de paginación y ordenamiento para los listados."""
from __future__ import annotations

from sqlalchemy import select, func, asc, desc
from sqlalchemy.orm import Session


def paginar(db: Session, base_query, *, model, columnas: dict, limit: int, offset: int,
            sort: str | None, order: str) -> dict:
    """Ejecuta `base_query` paginada y ordenada. Devuelve {total, items, limit, offset}.

    `columnas` mapea nombres de sort permitidos -> columnas del modelo.
    """
    total = db.scalar(select(func.count()).select_from(base_query.subquery())) or 0
    q = base_query
    if sort and sort in columnas:
        col = columnas[sort]
        q = q.order_by(desc(col) if order == "desc" else asc(col))
    q = q.limit(min(limit, 200)).offset(max(offset, 0))
    items = db.scalars(q).all()
    return {"total": total, "limit": limit, "offset": offset, "items": items}
