"""Registro y consulta de auditoría (VFP: auditoria)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.services import auditoria_central as central


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


OPERACION_CENTRAL = {"ALTA": "ALTA", "CREAR": "ALTA", "CREACION": "ALTA", "MODIFICAR": "MODIFICACION",
                     "MODIFICACION": "MODIFICACION", "EDITAR": "MODIFICACION", "BAJA": "BAJA",
                     "BORRAR": "BAJA", "ELIMINAR": "BAJA", "ANULAR": "BAJA"}


def registrar_cambio(db: Session, *, usuario: str, entidad: str, operacion: str,
                     entidad_id: str = "", perfil: str = "", ip: str = "",
                     antes: dict | None = None, despues: dict | None = None,
                     resultado: str = "OK", detalle: str = "", request_id: str = "") -> None:
    """Registra una mutación con su diff (acá y en la Auditoría central). Nunca interrumpe el negocio."""
    try:
        a, d = _norm(antes), _norm(despues)
        central.registrar(usuario=usuario, operacion=OPERACION_CENTRAL.get(operacion.upper(), "ACCION"),
                          entidad=entidad, entidad_id=str(entidad_id), descripcion=operacion,
                          cambios=_diff(a, d), detalle=detalle, ip=ip, request_id=request_id,
                          exito=resultado == "OK")
        db.add(models.AuditoriaCambio(
            usuario=(usuario or "anonimo")[:40], perfil=(perfil or "")[:8], ip=(ip or "")[:64],
            entidad=entidad[:40], entidad_id=str(entidad_id)[:40], operacion=operacion[:30],
            resultado=resultado[:12], detalle=(detalle or "")[:300],
            datos_anteriores=a, datos_nuevos=d, cambios=(_diff(a, d) or None)))
        db.commit()
    except Exception:
        db.rollback()


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
