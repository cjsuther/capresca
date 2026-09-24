"""Las solicitudes que una resolución de Despacho otorga (API interna, no pasa por el gateway).

El acto administrativo lo emite Despacho, pero las solicitudes son de Créditos: quien manda sobre
ellas es este módulo. Despacho pregunta cuáles están listas para entrar en un anexo, las asigna en
lote y, si hace falta, las saca. Acá se valida lo único que Despacho no puede saber: que una
solicitud esté realmente aprobada y que no quede otorgada por dos resoluciones distintas.

Entran al anexo las solicitudes **APROBADAS** y todavía sin originar: la resolución es el acto que
las otorga formalmente, antes de que se conviertan en contrato. El "lote" ES el número de la
resolución, como en el sistema anterior.
"""
from __future__ import annotations

import hmac
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, models_productos as m
from app.core.config import get_settings
from app.core.database import get_db

router = APIRouter(prefix="/internal/creditos/anexo", tags=["internal"])

APROBADA = "APROBADA"


def api_despacho(x_api_key: str | None = Header(None, alias="X-Api-Key")) -> None:
    clave = get_settings().despacho_internal_api_key
    if not clave or not x_api_key or not hmac.compare_digest(x_api_key, clave):
        raise HTTPException(401, "API interna: clave inválida.")


class AsignarIn(BaseModel):
    solicitud_ids: list[str]
    numero_resolucion: int
    fecha_resolucion: date | None = None


class QuitarIn(BaseModel):
    solicitud_ids: list[str]


def _nombre(db: Session, s: m.PPSolicitud) -> str:
    if s.solicitante_tipo == "REGISTRADO" and s.cliente_id:
        cli = db.get(models.Cliente, s.cliente_id)
        if cli:
            return cli.apellido_nombre
    return (s.cliente_datos or {}).get("apellido_nombre") or "Sin nombre"


def _documento(db: Session, s: m.PPSolicitud, campo: str) -> str:
    if s.solicitante_tipo == "REGISTRADO" and s.cliente_id:
        cli = db.get(models.Cliente, s.cliente_id)
        if cli:
            return getattr(cli, campo, "") or ""
    return (s.cliente_datos or {}).get(campo) or ""


def _fila(db: Session, s: m.PPSolicitud, producto: str) -> dict:
    return {"id": s.id, "numero": s.numero,
            "fecha_solicitud": s.creado_en.date() if s.creado_en else None,
            "cuil": _documento(db, s, "cuil"), "apellido_nombre": _nombre(db, s),
            "dni": _documento(db, s, "dni"), "monto": s.monto_solicitado,
            "producto_id": s.producto_id, "producto": producto or "", "estado": s.estado,
            "lote": s.lote_resolucion, "numero_resolucion": s.numero_resolucion,
            "en_resolucion": s.en_resolucion}


@router.get("/tipos", dependencies=[Depends(api_despacho)])
def tipos(db: Session = Depends(get_db)):
    """Los grupos por los que se arma un anexo: hoy, los productos de crédito."""
    filas = db.query(m.PPProducto).order_by(m.PPProducto.nombre).all()
    return [{"tipo": p.id, "nombre": p.nombre} for p in filas]


@router.get("/solicitudes", dependencies=[Depends(api_despacho)])
def solicitudes(producto_id: str | None = None, lote: int | None = Query(None, ge=1),
                db: Session = Depends(get_db)):
    """Con `lote`, las de esa resolución (para reimprimir el anexo). Sin él, las candidatas:
    aprobadas y todavía sin resolución."""
    q = db.query(m.PPSolicitud, m.PPProducto.nombre).outerjoin(
        m.PPProducto, m.PPProducto.id == m.PPSolicitud.producto_id)
    if lote:
        q = q.filter(m.PPSolicitud.lote_resolucion == lote,
                     m.PPSolicitud.en_resolucion.is_(True))
    else:
        q = q.filter(m.PPSolicitud.estado == APROBADA, m.PPSolicitud.en_resolucion.is_(False))
        if producto_id:
            q = q.filter(m.PPSolicitud.producto_id == producto_id)
    filas = q.order_by(m.PPSolicitud.creado_en).all()
    items = [_fila(db, s, nombre) for s, nombre in filas]
    return {"items": items, "cantidad": len(items),
            "total": sum((Decimal(str(i["monto"] or 0)) for i in items), Decimal("0"))}


@router.post("/asignar", dependencies=[Depends(api_despacho)])
def asignar(datos: AsignarIn, db: Session = Depends(get_db)):
    if not datos.solicitud_ids:
        raise HTTPException(422, "Elegí al menos una solicitud.")
    sols = (db.query(m.PPSolicitud)
            .filter(m.PPSolicitud.id.in_(datos.solicitud_ids)).with_for_update().all())
    if len(sols) != len(set(datos.solicitud_ids)):
        raise HTTPException(422, "Alguna de las solicitudes no existe.")
    # Sólo se otorga lo aprobado: una resolución no puede alcanzar algo todavía en evaluación.
    sin_aprobar = [s.numero for s in sols if s.estado != APROBADA]
    if sin_aprobar:
        raise HTTPException(422, f"Estas solicitudes no están aprobadas: {sin_aprobar}.")
    # Una solicitud no puede estar otorgada por dos resoluciones distintas.
    ajenas = [s.numero for s in sols
              if s.en_resolucion and s.numero_resolucion != datos.numero_resolucion]
    if ajenas:
        raise HTTPException(422, f"Estas solicitudes ya están en otra resolución: {ajenas}.")

    fecha = datos.fecha_resolucion or date.today()
    for s in sols:
        s.numero_resolucion = datos.numero_resolucion
        s.lote_resolucion = datos.numero_resolucion
        s.fecha_resolucion = fecha
        s.en_resolucion = True
    db.commit()
    return {"asignadas": len(sols),
            "total": sum((s.monto_solicitado or Decimal("0")) for s in sols) or Decimal("0")}


@router.post("/quitar", dependencies=[Depends(api_despacho)])
def quitar(datos: QuitarIn, db: Session = Depends(get_db)):
    """Despacho ya verificó que el instrumento siga en borrador: un acto emitido no se toca."""
    sols = (db.query(m.PPSolicitud)
            .filter(m.PPSolicitud.id.in_(datos.solicitud_ids)).with_for_update().all())
    for s in sols:
        s.numero_resolucion = 0
        s.lote_resolucion = 0
        s.fecha_resolucion = None
        s.en_resolucion = False
    db.commit()
    return {"quitadas": len(sols)}
