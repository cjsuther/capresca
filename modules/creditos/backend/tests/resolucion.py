"""Otorga una solicitud como lo hace Despacho: la pone en un lote y le asigna una resolución.

Originar desde una solicitud exige que su lote ya tenga resolución: los tests que originan la
otorgan primero con esto. No mira si es liquidable (eso lo prueban los tests de lotes).
"""
from datetime import date

from app import models_productos as m
from app.core.database import SessionLocal
from app.services import lotes_liquidacion as lotes


def otorgar(sid: str, numero: int = 1) -> int:
    with SessionLocal() as db:
        s = db.get(m.PPSolicitud, sid)
        lote = (db.get(m.PPLoteLiquidacion, s.lote_liquidacion_id) if s.lote_liquidacion_id
                else lotes._tomar(db, s.producto_id, lotes.fecha_de(s), lotes.maximo(db)))
        s.lote_liquidacion_id = lote.id
        lote.estado = lotes.CON_RESOLUCION
        lote.resolucion_id, lote.resolucion_numero = 1000 + numero, numero
        lote.resolucion_anio, lote.resolucion_fecha = date.today().year, date.today()
        db.flush()
        lotes._sync_solicitudes(db, lote)
        db.commit()
        return lote.id
