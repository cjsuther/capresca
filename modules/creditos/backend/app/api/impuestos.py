"""Impuestos para el armado de productos (componente TAX). Se administran en el módulo
Configuraciones; acá sólo se leen (el alta/edición no existe en Créditos)."""
from fastapi import APIRouter, Depends, Query

from app.core import configuraciones as config
from app.deps import get_current_user

router = APIRouter(prefix="/api/creditos/impuestos", tags=["impuestos"],
                   dependencies=[Depends(get_current_user)])


@router.get("")
def listar(estado: str = Query("todos", pattern="^(activos|todos)$")):
    items = config.impuestos(estado)
    return {"items": items, "total": len(items)}
