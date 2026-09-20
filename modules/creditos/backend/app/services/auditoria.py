"""Registro y consulta de auditoría (VFP: auditoria)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import models


def registrar(db: Session, *, usuario: str, proceso: str, opcion: str = "",
              perfil: str = "", maquina: str = "", sistema: str = "CCyPP") -> None:
    """Registra un evento de auditoría (no interrumpe el flujo ante error)."""
    try:
        db.add(models.EventoAuditoria(
            usuario=usuario[:40], proceso=proceso[:60], opcion=opcion[:80],
            perfil=perfil[:8], maquina=maquina[:40], sistema=sistema[:20]))
        db.commit()
    except Exception:
        db.rollback()


# --------------------- Auditoría de cambios (sistema nuevo) ---------------------
# Rastro rico de las mutaciones del sistema nuevo: antes/después + IP + resultado.

def ip_de(request) -> str:
    """IP de origen respetando el proxy (X-Forwarded-For), truncada a la columna."""
    fwd = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    ip = fwd or (request.client.host if request and request.client else "")
    return ip[:64]


def _norm(v: Any) -> Any:
    """Normaliza a tipos serializables/comparables (Decimal→str, date→iso…)."""
    return jsonable_encoder(v) if v is not None else None


def _diff(antes: dict | None, despues: dict | None) -> dict:
    """{campo: [antes, después]} sólo de las claves que cambian (o son nuevas)."""
    a, d = antes or {}, despues or {}
    cambios: dict[str, list] = {}
    for k in a.keys() | d.keys():
        if a.get(k) != d.get(k):
            cambios[k] = [a.get(k), d.get(k)]
    return cambios


def registrar_cambio(db: Session, *, usuario: str, entidad: str, operacion: str,
                     entidad_id: str = "", perfil: str = "", ip: str = "",
                     antes: dict | None = None, despues: dict | None = None,
                     resultado: str = "OK", detalle: str = "") -> None:
    """Registra una mutación con su diff. Nunca interrumpe el flujo de negocio."""
    try:
        a, d = _norm(antes), _norm(despues)
        db.add(models.AuditoriaCambio(
            usuario=(usuario or "anonimo")[:40], perfil=(perfil or "")[:8], ip=(ip or "")[:64],
            entidad=entidad[:40], entidad_id=str(entidad_id)[:40], operacion=operacion[:30],
            resultado=resultado[:12], detalle=(detalle or "")[:300],
            datos_anteriores=a, datos_nuevos=d, cambios=(_diff(a, d) or None)))
        db.commit()
    except Exception:
        db.rollback()


def consultar_cambios(db: Session, *, texto: str | None = None, entidad: str | None = None,
                      operacion: str | None = None, resultado: str | None = None,
                      desde: date | None = None, hasta: date | None = None,
                      limit: int = 25, offset: int = 0) -> dict:
    """Sobre paginado {total, limit, offset, items} del rastro de cambios."""
    A = models.AuditoriaCambio
    q = select(A)
    if texto:
        like = f"%{texto.strip()}%"
        q = q.where(or_(A.usuario.ilike(like), A.entidad.ilike(like),
                        A.entidad_id.ilike(like), A.detalle.ilike(like)))
    if entidad:
        q = q.where(A.entidad == entidad)
    if operacion:
        q = q.where(A.operacion == operacion)
    if resultado:
        q = q.where(A.resultado == resultado)
    if desde:
        q = q.where(A.fecha_hora >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.where(A.fecha_hora <= datetime.combine(hasta, datetime.max.time()))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(A.fecha_hora.desc(), A.id.desc()).limit(min(limit, 200)).offset(max(offset, 0))
    ).all()
    items = [{"id": e.id, "fecha_hora": e.fecha_hora, "usuario": e.usuario, "perfil": e.perfil,
              "ip": e.ip, "entidad": e.entidad, "entidad_id": e.entidad_id,
              "operacion": e.operacion, "resultado": e.resultado, "detalle": e.detalle}
             for e in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def obtener_cambio(db: Session, cambio_id: int) -> dict | None:
    """Detalle de un evento con el diff antes/después completo."""
    e = db.get(models.AuditoriaCambio, cambio_id)
    if not e:
        return None
    return {"id": e.id, "fecha_hora": e.fecha_hora, "usuario": e.usuario, "perfil": e.perfil,
            "ip": e.ip, "entidad": e.entidad, "entidad_id": e.entidad_id,
            "operacion": e.operacion, "resultado": e.resultado, "detalle": e.detalle,
            "datos_anteriores": e.datos_anteriores, "datos_nuevos": e.datos_nuevos,
            "cambios": e.cambios}


def consultar(db: Session, *, usuario: str | None = None,
              desde: date | None = None, hasta: date | None = None,
              limit: int = 25, offset: int = 0) -> dict:
    """Devuelve el sobre paginado {total, limit, offset, items} del log."""
    q = select(models.EventoAuditoria)
    if usuario:
        q = q.where(models.EventoAuditoria.usuario.like(f"%{usuario.upper()}%"))
    if desde:
        q = q.where(models.EventoAuditoria.fecha_hora >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.where(models.EventoAuditoria.fecha_hora <= datetime.combine(hasta, datetime.max.time()))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(models.EventoAuditoria.fecha_hora.desc())
        .limit(min(limit, 200)).offset(max(offset, 0))
    ).all()
    items = [{"fecha_hora": e.fecha_hora, "usuario": e.usuario, "maquina": e.maquina,
              "sistema": e.sistema, "perfil": e.perfil, "proceso": e.proceso,
              "opcion": e.opcion} for e in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def resumen(db: Session, *, por: str = "usuario",
            desde: date | None = None, hasta: date | None = None) -> dict:
    """Auditoría agrupada por usuario (X3005) o por máquina (X3010): eventos por
    cada uno, con perfiles y primer/último evento del rango. Sobre la muestra
    real cargada (últimos ~50 mil eventos del log en producción)."""
    A = models.EventoAuditoria
    col = A.maquina if por == "maquina" else A.usuario
    q = select(col, func.count(),
               func.count(func.distinct(A.proceso)),
               func.min(A.fecha_hora), func.max(A.fecha_hora))
    if desde:
        q = q.where(A.fecha_hora >= datetime.combine(desde, datetime.min.time()))
    if hasta:
        q = q.where(A.fecha_hora <= datetime.combine(hasta, datetime.max.time()))
    q = q.group_by(col).order_by(func.count().desc())
    filas, total = [], 0
    for clave, n, nproc, primero, ultimo in db.execute(q).all():
        total += int(n)
        filas.append({"clave": (clave or "").strip() or "—", "eventos": int(n),
                      "procesos_distintos": int(nproc), "primero": primero, "ultimo": ultimo})
    return {"por": por, "desde": desde, "hasta": hasta,
            "total_eventos": total, "cantidad": len(filas), "items": filas}
