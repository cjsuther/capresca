"""Las solicitudes que una resolución de Despacho otorga (API interna, no pasa por el gateway).

El acto administrativo lo emite Despacho, pero las solicitudes son de Créditos: quien manda sobre
ellas es este módulo. Despacho pregunta cuáles están listas para entrar en un anexo, las asigna en
lote y, si hace falta, las saca. Acá se valida lo único que Despacho no puede saber: que una
solicitud no quede otorgada por dos resoluciones distintas.

El "lote" ES el número de la resolución, como en el sistema anterior.
"""
from __future__ import annotations

import hmac
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models as m
from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/internal/creditos/anexo", tags=["internal"])

APROBADA = "A"
CUBICADAS = ("C", "DC")     # cubicada / descubicada-cubicada: hay fondos asignados


def api_despacho(x_api_key: str | None = Header(None, alias="X-Api-Key")) -> None:
    clave = get_settings().despacho_internal_api_key
    if not clave or not x_api_key or not hmac.compare_digest(x_api_key, clave):
        raise HTTPException(401, "API interna: clave inválida.")


class AsignarIn(BaseModel):
    solicitud_ids: list[int]
    numero_resolucion: int
    fecha_resolucion: date | None = None


class QuitarIn(BaseModel):
    solicitud_ids: list[int]


def _fila(s: m.SolicitudCredito, linea_nombre: str) -> dict:
    return {"id": s.id, "fecha_solicitud": s.fecha_soli, "cuil": s.cuil,
            "apellido_nombre": s.apellido_nombre, "dni": s.dni, "monto": s.montosol,
            "linea": s.linea, "linea_nombre": linea_nombre or "", "estado": s.estado,
            "cubica": s.cubica, "lote": s.lote, "numero_resolucion": s.no_resol,
            "en_resolucion": s.en_reso}


@router.get("/solicitudes", dependencies=[Depends(api_despacho)])
def solicitudes(linea_min: int | None = None, linea_max: int | None = None,
                cartera: int | None = None, lote: int | None = Query(None, ge=1),
                db: Session = Depends(get_db)):
    """Con `lote`, las de esa resolución (para reimprimir el anexo). Sin él, las candidatas:
    aprobadas, cubicadas y todavía sin resolución."""
    q = (db.query(m.SolicitudCredito, m.LineaCredito.nombre)
         .outerjoin(m.LineaCredito, m.LineaCredito.id == m.SolicitudCredito.linea))
    if lote:
        q = q.filter(m.SolicitudCredito.lote == lote, m.SolicitudCredito.en_reso.is_(True))
    else:
        q = q.filter(m.SolicitudCredito.estado == APROBADA,
                     m.SolicitudCredito.cubica.in_(CUBICADAS),
                     m.SolicitudCredito.en_reso.is_(False))
        if cartera is not None:
            q = q.filter(m.LineaCredito.cartera == cartera)
        elif linea_min is not None and linea_max is not None:
            q = q.filter(m.SolicitudCredito.linea.between(linea_min, linea_max))
    filas = q.order_by(m.SolicitudCredito.linea, m.SolicitudCredito.apellido_nombre).all()
    items = [_fila(s, nombre) for s, nombre in filas]
    return {"items": items, "cantidad": len(items),
            "total": sum((Decimal(str(i["monto"] or 0)) for i in items), Decimal("0"))}


@router.post("/asignar", dependencies=[Depends(api_despacho)])
def asignar(datos: AsignarIn, db: Session = Depends(get_db)):
    if not datos.solicitud_ids:
        raise HTTPException(422, "Elegí al menos una solicitud.")
    sols = (db.query(m.SolicitudCredito)
            .filter(m.SolicitudCredito.id.in_(datos.solicitud_ids)).all())
    if len(sols) != len(set(datos.solicitud_ids)):
        raise HTTPException(422, "Alguna de las solicitudes no existe.")
    # Una solicitud no puede estar otorgada por dos resoluciones distintas.
    ajenas = [s.id for s in sols if s.en_reso and s.no_resol != datos.numero_resolucion]
    if ajenas:
        raise HTTPException(422, f"Estas solicitudes ya están en otra resolución: {ajenas}.")

    fecha = datos.fecha_resolucion or date.today()
    for s in sols:
        s.no_resol = datos.numero_resolucion
        s.lote = datos.numero_resolucion
        s.fecha_resol = fecha
        s.en_reso = True
    db.commit()
    return {"asignadas": len(sols),
            "total": sum((s.montosol or Decimal("0")) for s in sols) or Decimal("0")}


@router.post("/quitar", dependencies=[Depends(api_despacho)])
def quitar(datos: QuitarIn, db: Session = Depends(get_db)):
    """Despacho ya verificó que el instrumento siga en borrador: un acto emitido no se toca."""
    sols = (db.query(m.SolicitudCredito)
            .filter(m.SolicitudCredito.id.in_(datos.solicitud_ids)).all())
    for s in sols:
        s.no_resol = 0
        s.lote = 0
        s.fecha_resol = None
        s.en_reso = False
    db.commit()
    return {"quitadas": len(sols)}
