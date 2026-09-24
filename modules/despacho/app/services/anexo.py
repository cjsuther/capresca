"""Anexo de resolución: el vínculo entre Despacho y Créditos.

Las solicitudes aprobadas se asignan EN LOTE a una resolución, que es la que las otorga
formalmente. El "lote" ES el número correlativo de la resolución, como en el sistema anterior.

Los tipos de anexo agrupan por rango de línea de crédito (del formulario VFP del anexo).
"""
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SERIE_POR_DEFECTO, Resolucion, SolicitudAnexo

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


def _filtrar_por_tipo(q, tipo: int):
    cfg = TIPOS_ANEXO.get(tipo, TIPOS_ANEXO[6])
    if cfg.get("todos"):
        return q
    if "cartera" in cfg:
        return q.where(SolicitudAnexo.cartera == cfg["cartera"])
    return q.where(SolicitudAnexo.linea.between(cfg["linea_min"], cfg["linea_max"]))


def candidatas(db: Session, tipo: int, lote: int | None = None) -> dict:
    """Las que todavía no están en ninguna resolución (aprobadas y cubicadas), o las de un lote ya
    asignado, para reimprimir el anexo."""
    q = select(SolicitudAnexo)
    if lote:
        q = q.where(SolicitudAnexo.lote == lote, SolicitudAnexo.en_resolucion.is_(True))
    else:
        q = q.where(SolicitudAnexo.estado == "A", SolicitudAnexo.cubica.in_(("C", "DC")),
                    SolicitudAnexo.en_resolucion.is_(False))
        q = _filtrar_por_tipo(q, tipo)
    filas = list(db.scalars(q.order_by(SolicitudAnexo.linea, SolicitudAnexo.apellido_nombre)).all())
    return {"tipo": tipo, "nombre": TIPOS_ANEXO.get(tipo, {}).get("nombre", ""),
            "cantidad": len(filas), "total": sum((f.monto for f in filas), Decimal("0")),
            "items": filas}


def asignar(db: Session, *, tipo: int, resolucion_id: int, solicitud_ids: list[int]) -> dict:
    """Mete las solicitudes elegidas en el anexo de la resolución."""
    if not solicitud_ids:
        raise HTTPException(422, "Elegí al menos una solicitud.")
    r = db.get(Resolucion, resolucion_id)
    if r is None:
        raise HTTPException(404, "Resolución no encontrada")
    if r.anulada:
        raise HTTPException(422, "La resolución está anulada.")

    sols = list(db.scalars(select(SolicitudAnexo).where(SolicitudAnexo.id.in_(solicitud_ids))).all())
    if len(sols) != len(set(solicitud_ids)):
        raise HTTPException(422, "Alguna de las solicitudes no existe.")
    # Una solicitud no puede estar otorgada por dos resoluciones distintas.
    ajenas = [s.id for s in sols if s.en_resolucion and s.numero_resolucion != r.numero]
    if ajenas:
        raise HTTPException(422, f"Estas solicitudes ya están en otra resolución: {ajenas}.")

    for s in sols:
        s.lote = r.numero
        s.numero_resolucion = r.numero
        s.fecha_resolucion = r.fecha
        s.en_resolucion = True
    db.commit()
    return {"tipo": tipo, "resolucion_id": r.id, "numero": r.numero, "anio": r.anio,
            "fecha": r.fecha, "asignadas": len(sols),
            "total": sum((s.monto for s in sols), Decimal("0"))}


def quitar(db: Session, solicitud_ids: list[int]) -> dict:
    """Saca solicitudes del anexo (mientras la resolución siga en borrador)."""
    sols = list(db.scalars(select(SolicitudAnexo).where(SolicitudAnexo.id.in_(solicitud_ids))).all())
    for s in sols:
        # El anexo es de créditos: su serie es la general.
        r = db.scalar(select(Resolucion).where(Resolucion.numero == s.numero_resolucion,
                                               Resolucion.serie == SERIE_POR_DEFECTO))
        if r is not None and r.oficial:
            raise HTTPException(422,
                                f"La solicitud {s.id} está en un instrumento ya emitido: no se saca.")
        s.lote = 0
        s.numero_resolucion = 0
        s.fecha_resolucion = None
        s.en_resolucion = False
    db.commit()
    return {"quitadas": len(sols)}
