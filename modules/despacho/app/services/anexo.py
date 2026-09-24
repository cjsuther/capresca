"""Anexo de resolución: el vínculo entre Despacho y Créditos.

Las solicitudes aprobadas se asignan EN LOTE a una resolución, que es la que las otorga
formalmente. El "lote" ES el número correlativo de la resolución, como en el sistema anterior.

Las solicitudes no se guardan acá: son de Créditos y se consultan por su API interna. Despacho pone
la regla del instrumento (un acto emitido no se toca) y Créditos la de la solicitud (no puede estar
otorgada por dos resoluciones).

El anexo se arma por producto de crédito (en el sistema anterior eran rangos de línea; hoy el
circuito vivo son los productos, y los publica Créditos).
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SERIE_POR_DEFECTO, Resolucion
from app.services import creditos_central

TODOS = ""     # sin filtrar por producto


def tipos() -> list[dict]:
    """Los productos por los que se puede agrupar, más la opción de traerlos todos."""
    return [{"tipo": TODOS, "nombre": "Todos los productos"}] + creditos_central.tipos()


def candidatas(db: Session, tipo: str = TODOS, lote: int | None = None) -> dict:
    """Las aprobadas que todavía no están en ninguna resolución, o las de un lote ya asignado,
    para reimprimir el anexo."""
    d = (creditos_central.candidatas(lote=lote) if lote
         else creditos_central.candidatas(producto_id=tipo or None))
    nombre = next((t["nombre"] for t in tipos() if t["tipo"] == tipo), "") if tipo else "Todos los productos"
    return {"tipo": tipo, "nombre": nombre, "cantidad": d.get("cantidad", 0),
            "total": Decimal(str(d.get("total") or 0)), "items": d.get("items", [])}


def asignar(db: Session, *, tipo: str, resolucion_id: int, solicitud_ids: list[str]) -> dict:
    """Mete las solicitudes elegidas en el anexo de la resolución."""
    if not solicitud_ids:
        raise HTTPException(422, "Elegí al menos una solicitud.")
    r = db.get(Resolucion, resolucion_id)
    if r is None:
        raise HTTPException(404, "Resolución no encontrada")
    if r.anulada:
        raise HTTPException(422, "La resolución está anulada.")

    d = creditos_central.asignar(solicitud_ids=solicitud_ids, numero_resolucion=r.numero,
                                 fecha_resolucion=r.fecha)
    return {"tipo": tipo, "resolucion_id": r.id, "numero": r.numero, "anio": r.anio,
            "fecha": r.fecha, "asignadas": d.get("asignadas", 0),
            "total": Decimal(str(d.get("total") or 0))}


def quitar(db: Session, solicitud_ids: list[str], *, numero_resolucion: int | None = None) -> dict:
    """Saca solicitudes del anexo (mientras la resolución siga en borrador)."""
    if not solicitud_ids:
        return {"quitadas": 0}
    if numero_resolucion:
        # El anexo es de créditos: su serie es la general.
        r = db.scalar(select(Resolucion).where(Resolucion.numero == numero_resolucion,
                                               Resolucion.serie == SERIE_POR_DEFECTO))
        if r is not None and r.oficial:
            raise HTTPException(422, "El instrumento ya fue emitido: no se saca nada del anexo.")
    return creditos_central.quitar(solicitud_ids)
