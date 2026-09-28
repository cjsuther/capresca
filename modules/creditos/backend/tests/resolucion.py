"""Pone una solicitud en el anexo de una resolución, como hace Despacho por la API interna.

Originar desde una solicitud exige que ya esté en una resolución: los tests que originan la
otorgan primero con esto.
"""
from datetime import date

from app import models_productos as m
from app.core.database import SessionLocal


def otorgar(sid: str, numero: int = 1) -> None:
    with SessionLocal() as db:
        s = db.get(m.PPSolicitud, sid)
        s.numero_resolucion = s.lote_resolucion = numero
        s.fecha_resolucion = date.today()
        s.en_resolucion = True
        db.commit()
