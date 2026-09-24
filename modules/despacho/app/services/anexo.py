"""Anexo de resolución: el vínculo entre Despacho y Créditos.

Las solicitudes aprobadas se asignan EN LOTE a una resolución, que es la que las otorga
formalmente. El "lote" ES el número correlativo de la resolución, como en el sistema anterior.

Las solicitudes no se guardan acá: son de Créditos y se consultan por su API interna. Despacho pone
la regla del instrumento (un acto emitido no se toca) y Créditos la de la solicitud (no puede estar
otorgada por dos resoluciones).

Los tipos de anexo agrupan por rango de línea de crédito (del formulario VFP del anexo).
"""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SERIE_POR_DEFECTO, Resolucion
from app.services import creditos_central

TIPOS_ANEXO = {
    1: {"nombre": "AGAP", "linea_min": 8050, "linea_max": 8051},
    2: {"nombre": "Microcréditos", "linea_min": 6810, "linea_max": 6813},
    3: {"nombre": "Productivos", "linea_min": 6800, "linea_max": 6801},
    4: {"nombre": "Vivienda", "linea_min": 8130, "linea_max": 8133},
    5: {"nombre": "Gas", "cartera": 11},
    6: {"nombre": "Resto", "todos": True},
}


def tipos() -> list[dict]:
    return [{"tipo": t, "nombre": cfg["nombre"]} for t, cfg in TIPOS_ANEXO.items()]


def _filtro(tipo: int) -> dict:
    """Qué solicitudes pide cada tipo de anexo. 'Resto' no filtra: trae todo lo pendiente."""
    cfg = TIPOS_ANEXO.get(tipo, TIPOS_ANEXO[6])
    if cfg.get("todos"):
        return {}
    if "cartera" in cfg:
        return {"cartera": cfg["cartera"]}
    return {"linea_min": cfg["linea_min"], "linea_max": cfg["linea_max"]}


def candidatas(db: Session, tipo: int, lote: int | None = None) -> dict:
    """Las que todavía no están en ninguna resolución (aprobadas y cubicadas), o las de un lote ya
    asignado, para reimprimir el anexo."""
    d = (creditos_central.candidatas(lote=lote) if lote
         else creditos_central.candidatas(**_filtro(tipo)))
    return {"tipo": tipo, "nombre": TIPOS_ANEXO.get(tipo, {}).get("nombre", ""),
            "cantidad": d.get("cantidad", 0), "total": Decimal(str(d.get("total") or 0)),
            "items": d.get("items", [])}


def asignar(db: Session, *, tipo: int, resolucion_id: int, solicitud_ids: list[int]) -> dict:
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


def quitar(db: Session, solicitud_ids: list[int], *, numero_resolucion: int | None = None) -> dict:
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
