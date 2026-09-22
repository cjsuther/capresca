"""Índices de referencia para líneas de tasa variable (tasa = índice + margen). Se administran en el
módulo Configuraciones; acá sólo se leen."""
from fastapi import APIRouter, Depends, Query

from app.core import configuraciones as config
from app.deps import get_current_user

router = APIRouter(prefix="/api/creditos/indices", tags=["indices"],
                   dependencies=[Depends(get_current_user)])


@router.get("")
def listar(estado: str = Query("todos", pattern="^(activos|todos)$")):
    items = config.indices(estado)
    return {"items": items, "total": len(items)}
