"""Servicios del módulo Mesa de entradas: turnos de atención.

Estados del turno: E (en espera) → L (llamado) → A (atendido); E/L → C (cancelado).
La numeración es correlativa por día.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import models


class ReglaNegocioError(Exception):
    pass


def _proximo_numero(db: Session, fecha: date) -> int:
    n = db.scalar(select(func.max(models.Turno.numero)).where(models.Turno.fecha == fecha))
    return (n or 0) + 1


def generar_turno(db: Session, *, tipo_tramite_id: int, cliente_nombre: str = "",
                  cliente_cuil: str = "", fecha: date | None = None) -> models.Turno:
    tt = db.get(models.TipoTramite, tipo_tramite_id)
    if not tt or not tt.activo:
        raise ReglaNegocioError("Tipo de trámite inexistente o inactivo")
    f = fecha or date.today()
    from app.core.numbering import crear_con_numero_unico

    def _construir(n):
        t = models.Turno(numero=n, fecha=f, tipo_tramite_id=tipo_tramite_id,
                         cliente_nombre=cliente_nombre, cliente_cuil=cliente_cuil, estado="E")
        db.add(t)
        return t
    turno = crear_con_numero_unico(db, lambda: _proximo_numero(db, f), _construir)  # árbitro DB (H-108)
    db.commit()
    db.refresh(turno)
    return turno


def llamar_siguiente(db: Session, *, box: str, fecha: date | None = None,
                     tipo_tramite_id: int | None = None) -> models.Turno | None:
    """Llama al siguiente turno en espera (FIFO por número). Devuelve None si no hay."""
    f = fecha or date.today()
    qy = select(models.Turno).where(models.Turno.fecha == f, models.Turno.estado == "E")
    if tipo_tramite_id:
        qy = qy.where(models.Turno.tipo_tramite_id == tipo_tramite_id)
    turno = db.scalars(qy.order_by(models.Turno.numero).limit(1)).first()
    if not turno:
        return None
    turno.estado = "L"
    turno.box = box
    db.commit()
    db.refresh(turno)
    return turno


def atender_turno(db: Session, turno_id: int) -> models.Turno:
    t = db.get(models.Turno, turno_id)
    if not t:
        raise ReglaNegocioError("Turno inexistente")
    if t.estado not in ("E", "L"):
        raise ReglaNegocioError("El turno no está en espera ni llamado")
    t.estado = "A"
    t.atendido = datetime.now()
    db.commit()
    db.refresh(t)
    return t


def cancelar_turno(db: Session, turno_id: int) -> models.Turno:
    t = db.get(models.Turno, turno_id)
    if not t:
        raise ReglaNegocioError("Turno inexistente")
    if t.estado == "A":
        raise ReglaNegocioError("No se puede cancelar un turno ya atendido")
    t.estado = "C"
    db.commit()
    db.refresh(t)
    return t


def tablero(db: Session, fecha: date) -> dict:
    """Estado de la cola del día: en espera, llamados y contadores."""
    turnos = db.scalars(select(models.Turno).where(models.Turno.fecha == fecha)
                        .order_by(models.Turno.numero)).all()
    def resumen(t):
        return {"id": t.id, "numero": t.numero, "tipo": t.tipo_tramite.nombre,
                "cliente": t.cliente_nombre, "estado": t.estado, "box": t.box}
    return {
        "fecha": fecha,
        "en_espera": [resumen(t) for t in turnos if t.estado == "E"],
        "llamados": [resumen(t) for t in turnos if t.estado == "L"],
        "atendidos": sum(1 for t in turnos if t.estado == "A"),
        "cancelados": sum(1 for t in turnos if t.estado == "C"),
    }
