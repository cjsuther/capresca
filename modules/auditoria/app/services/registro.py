"""Alta de eventos y consulta del registro."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.services import enmascarar

# Del método HTTP se deduce qué le pasó al dato cuando el módulo no lo aclara.
POR_METODO = {"POST": "ALTA", "PUT": "MODIFICACION", "PATCH": "MODIFICACION", "DELETE": "BAJA"}


def operacion_de(metodo: str, ruta: str, declarada: str | None = None) -> str:
    if declarada in models.OPERACIONES:
        return declarada
    op = POR_METODO.get((metodo or "").upper(), "ACCION")
    # Un POST a /aprobar, /enviar, /publicar… no da de alta nada: es una acción de negocio.
    if op == "ALTA" and any(p in (ruta or "") for p in (
            "/aprobar", "/rechazar", "/enviar", "/publicar", "/retirar", "/reactivar", "/estado",
            "/actualizar", "/reintentar", "/resolver", "/liquidar", "/desembolsar", "/excluir",
            "/incluir", "/login", "/logout", "/simular", "/importar", "/copiar")):
        op = "ACCION"
    return op


def registrar(db: Session, datos: dict) -> models.Evento:
    ruta = str(datos.get("ruta") or "")[:300]
    metodo = str(datos.get("metodo") or "").upper()[:8]
    estado = datos.get("estado_http")
    e = models.Evento(
        usuario=str(datos.get("usuario") or "")[:60],
        usuario_id=datos.get("usuario_id"),
        ip=str(datos.get("ip") or "")[:64],
        modulo=str(datos.get("modulo") or "")[:30],
        operacion=operacion_de(metodo, ruta, datos.get("operacion")),
        entidad=str(datos.get("entidad") or "")[:60],
        entidad_id=str(datos.get("entidad_id") or "")[:80],
        descripcion=str(datos.get("descripcion") or "")[:300],
        metodo=metodo, ruta=ruta, estado_http=estado,
        exito=datos.get("exito") if datos.get("exito") is not None else (estado is None or estado < 400),
        origen=datos.get("origen") if datos.get("origen") in models.ORIGENES else "MODULO",
        request_id=str(datos.get("request_id") or "")[:40],
        cambios=enmascarar.cambios(datos.get("cambios")),
        detalle=str(datos.get("detalle") or "")[:4000],
    )
    if datos.get("fecha"):
        e.fecha = datos["fecha"]
    db.add(e)
    return e


def buscar(db: Session, *, usuario="", modulo="", operacion="", entidad="", entidad_id="", texto="",
           desde: date | None = None, hasta: date | None = None, solo_errores=False,
           limit: int = 50, offset: int = 0) -> dict:
    q = select(models.Evento)
    if usuario:
        q = q.where(models.Evento.usuario.ilike(f"%{usuario}%"))
    if modulo:
        q = q.where(models.Evento.modulo == modulo)
    if operacion:
        q = q.where(models.Evento.operacion == operacion)
    if entidad:
        q = q.where(models.Evento.entidad == entidad)
    if entidad_id:
        q = q.where(models.Evento.entidad_id == entidad_id)
    if solo_errores:
        q = q.where(models.Evento.exito.is_(False))
    if desde:
        q = q.where(models.Evento.fecha >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.where(models.Evento.fecha < datetime.combine(hasta + timedelta(days=1), datetime.min.time()))
    if texto:
        t = f"%{texto}%"
        q = q.where(or_(models.Evento.descripcion.ilike(t), models.Evento.entidad_id.ilike(t),
                        models.Evento.ruta.ilike(t), models.Evento.detalle.ilike(t),
                        models.Evento.usuario.ilike(t)))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    filas = db.scalars(q.order_by(models.Evento.fecha.desc(), models.Evento.id.desc())
                        .limit(min(limit, 500)).offset(offset)).all()
    return {"items": [serial(e) for e in filas], "total": total, "limit": limit, "offset": offset}


def serial(e: models.Evento) -> dict:
    return {"id": e.id, "fecha": e.fecha.isoformat() if e.fecha else None, "usuario": e.usuario,
            "usuarioId": e.usuario_id, "ip": e.ip, "modulo": e.modulo, "operacion": e.operacion,
            "entidad": e.entidad, "entidadId": e.entidad_id, "descripcion": e.descripcion,
            "metodo": e.metodo, "ruta": e.ruta, "estadoHttp": e.estado_http, "exito": e.exito,
            "origen": e.origen, "requestId": e.request_id, "cambios": e.cambios or {}, "detalle": e.detalle}


def purgar(db: Session, dias: int | None = None) -> int:
    """Borra lo que supera la retención (5 años por defecto). Devuelve cuántos eventos se fueron."""
    corte = datetime.now(timezone.utc) - timedelta(days=dias or settings.retencion_dias)
    n = db.query(models.Evento).filter(models.Evento.fecha < corte).delete(synchronize_session=False)
    db.commit()
    return n
