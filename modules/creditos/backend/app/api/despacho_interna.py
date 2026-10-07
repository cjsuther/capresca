"""Los lotes que otorga una resolución de Despacho (API interna, no pasa por el gateway).

El acto administrativo lo emite Despacho, pero los lotes y sus solicitudes son de Créditos: quien
manda sobre ellos es este módulo. Despacho lista los lotes, les asigna la resolución que los otorga
(o se la quita mientras no se liquidaron) y avisa cuando cambia la resolución (N° oficial, fecha,
importe). Acá se controla lo que Despacho no puede saber: que un lote no reciba dos resoluciones y
que la suma de los lotes de una resolución no pase su importe (services/lotes_liquidacion).
"""
from __future__ import annotations

import hmac
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models, models_productos as m
from app.api.contratos import _nombre_solicitante, serial_lote
from app.core.config import get_settings
from app.core.database import get_db
from app.services import lotes_liquidacion as lotes

router = APIRouter(prefix="/internal/creditos/lotes", tags=["internal"])


def api_despacho(x_api_key: str | None = Header(None, alias="X-Api-Key")) -> None:
    clave = get_settings().despacho_internal_api_key
    if not clave or not x_api_key or not hmac.compare_digest(x_api_key, clave):
        raise HTTPException(401, "API interna: clave inválida.")


class ResolucionIn(BaseModel):
    id: int
    numero: int
    anio: int
    numero_oficial: int | None = None
    fecha: date | None = None
    importe: Decimal = Decimal("0")
    tipo: str = "RES"                 # RES | DIS


class AsignarIn(BaseModel):
    lote_ids: list[int]
    resolucion: ResolucionIn


def _r(r: ResolucionIn) -> dict:
    return {**r.model_dump(), "fecha": r.fecha.isoformat() if r.fecha else None}


def _documento(db: Session, s: m.PPSolicitud, campo: str) -> str:
    if s.solicitante_tipo == "REGISTRADO" and s.cliente_id:
        cli = db.get(models.Cliente, s.cliente_id)
        if cli:
            return getattr(cli, campo, "") or ""
    return (s.cliente_datos or {}).get(campo) or ""


@router.get("/tipos", dependencies=[Depends(api_despacho)])
def tipos(db: Session = Depends(get_db)):
    """Los tipos de crédito por los que se arman los lotes: los productos."""
    filas = db.query(m.PPProducto).order_by(m.PPProducto.nombre).all()
    return [{"tipo": p.id, "nombre": p.nombre} for p in filas]


@router.get("", dependencies=[Depends(api_despacho)])
def listar(estado: str | None = None, producto_id: str | None = None, resolucion_id: int | None = None,
           numero: int = 0, anio: int | None = None, db: Session = Depends(get_db)):
    """Lotes con solicitudes. Con `resolucion_id` (o número y año, para los migrados), los de esa
    resolución, con el total ya comprometido."""
    lotes.asignar_pendientes(db)
    if resolucion_id or (numero and anio):
        q = lotes._de_resolucion(db, resolucion_id, numero, anio)
    else:
        q = db.query(m.PPLoteLiquidacion)
    if estado:
        q = q.filter(m.PPLoteLiquidacion.estado == estado.upper())
    if producto_id:
        q = q.filter(m.PPLoteLiquidacion.producto_id == producto_id)
    nombres = dict(db.query(m.PPProducto.id, m.PPProducto.nombre).all())
    tope = lotes.maximo(db)
    items = [serial_lote(db, lt, nombres, tope=tope, detalle=False)
             for lt in q.order_by(m.PPLoteLiquidacion.anio.desc(), m.PPLoteLiquidacion.numero.desc()).all()]
    items = [x for x in items if x["cantidad"]]
    return {"items": items, "cantidad": len(items),
            "total": sum((Decimal(str(x["montoTotal"])) for x in items), Decimal("0"))}


@router.get("/resolucion/solicitudes", dependencies=[Depends(api_despacho)])
def solicitudes_de_resolucion(resolucion_id: int = Query(...), numero: int = 0, anio: int | None = None,
                              db: Session = Depends(get_db)):
    """Las solicitudes que otorga una resolución (las de sus lotes): el anexo impreso."""
    filas = []
    for lt in lotes._de_resolucion(db, resolucion_id, numero, anio).order_by(
            m.PPLoteLiquidacion.anio, m.PPLoteLiquidacion.numero).all():
        prod = db.get(m.PPProducto, lt.producto_id)
        for s, c in lotes.items(db, lt):
            filas.append({
                "id": s.id if s else c.id, "numero": s.numero if s else c.numero_contrato,
                "lote": lt.codigo,
                "fecha_solicitud": s.creado_en.date() if (s and s.creado_en) else c.fecha_valor,
                "cuil": _documento(db, s, "cuil") if s else "",
                "apellido_nombre": _nombre_solicitante(db, s) if s else c.cliente_nombre,
                "dni": _documento(db, s, "dni") if s else "",
                "monto": s.monto_solicitado if s else c.monto_original,
                "producto_id": lt.producto_id, "producto": prod.nombre if prod else "",
                "estado": s.estado if s else c.estado})
    return {"items": filas, "cantidad": len(filas),
            "total": sum((Decimal(str(f["monto"] or 0)) for f in filas), Decimal("0"))}


@router.get("/{lote_id}", dependencies=[Depends(api_despacho)])
def ver(lote_id: int, db: Session = Depends(get_db)):
    lt = db.get(m.PPLoteLiquidacion, lote_id)
    if lt is None:
        raise HTTPException(404, "Lote no encontrado.")
    return serial_lote(db, lt)


@router.post("/asignar-resolucion", dependencies=[Depends(api_despacho)])
def asignar_resolucion(datos: AsignarIn, db: Session = Depends(get_db)):
    asignados = lotes.asignar_resolucion(db, datos.lote_ids, _r(datos.resolucion))
    total = lotes.total_resolucion(db, datos.resolucion.id, datos.resolucion.numero, datos.resolucion.anio)
    return {"asignados": [lt.codigo for lt in asignados], "totalResolucion": total}


@router.post("/{lote_id}/quitar-resolucion", dependencies=[Depends(api_despacho)])
def quitar_resolucion(lote_id: int, db: Session = Depends(get_db)):
    """Despacho ya verificó que el acto todavía se puede tocar."""
    lt = lotes.quitar_resolucion(db, lote_id)
    return {"lote": lt.codigo, "estado": lt.estado}


@router.post("/resolucion", dependencies=[Depends(api_despacho)])
def resolucion_actualizada(r: ResolucionIn, db: Session = Depends(get_db)):
    """Despacho cambió la resolución: se actualiza la copia de sus lotes (409 si el importe nuevo no
    alcanza para los lotes que ya otorga)."""
    return {"lotes": lotes.actualizar_resolucion(db, _r(r)),
            "totalResolucion": lotes.total_resolucion(db, r.id, r.numero, r.anio)}
