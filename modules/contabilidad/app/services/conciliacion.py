"""Conciliación bancaria: el extracto del banco contra el mayor de la cuenta bancaria.

Cada línea del extracto se vincula con un movimiento del mayor (una línea de asiento). Lo que queda
sin pareja, de los dos lados, es la diferencia a explicar.

Signos: el extracto usa el criterio del banco (+ entrada, − salida); en el mayor de una cuenta de
activo, una entrada es DEBE y una salida es HABER.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.services.motor import ErrorContable

CERO = Decimal("0.00")


def _f(v) -> float:
    return float(v or 0)


def estado(db: Session, cuenta_codigo: str, *, desde: date | None = None, hasta: date | None = None) -> dict:
    cuenta = db.scalar(select(models.Cuenta).where(models.Cuenta.codigo == cuenta_codigo))
    if cuenta is None:
        raise ErrorContable(f"La cuenta {cuenta_codigo} no existe.")

    q_ext = select(models.LineaExtracto).where(models.LineaExtracto.cuenta_codigo == cuenta_codigo)
    q_mov = (select(models.AsientoLinea, models.Asiento)
             .join(models.Asiento, models.AsientoLinea.asiento_id == models.Asiento.id)
             .where(models.AsientoLinea.cuenta_codigo == cuenta_codigo,
                    models.Asiento.estado != "BORRADOR"))
    if desde:
        q_ext = q_ext.where(models.LineaExtracto.fecha >= desde)
        q_mov = q_mov.where(models.Asiento.fecha >= desde)
    if hasta:
        q_ext = q_ext.where(models.LineaExtracto.fecha <= hasta)
        q_mov = q_mov.where(models.Asiento.fecha <= hasta)

    extracto = db.scalars(q_ext.order_by(models.LineaExtracto.fecha, models.LineaExtracto.id)).all()
    movimientos = db.execute(q_mov.order_by(models.Asiento.fecha, models.Asiento.numero)).all()
    conciliadas = {e.asiento_linea_id for e in extracto if e.asiento_linea_id}

    saldo_extracto = sum((e.importe for e in extracto), CERO)
    saldo_mayor = sum((l.debe - l.haber for l, _a in movimientos), CERO)
    pend_ext = sum((e.importe for e in extracto if not e.asiento_linea_id), CERO)
    pend_may = sum((l.debe - l.haber for l, _a in movimientos if l.id not in conciliadas), CERO)

    return {
        "cuenta": {"codigo": cuenta.codigo, "nombre": cuenta.nombre},
        "extracto": [{"id": e.id, "fecha": e.fecha.isoformat(), "descripcion": e.descripcion,
                      "referencia": e.referencia, "importe": _f(e.importe),
                      "conciliada": e.asiento_linea_id is not None,
                      "asientoLineaId": e.asiento_linea_id, "conciliadaPor": e.conciliada_por}
                     for e in extracto],
        "movimientos": [{"asientoLineaId": l.id, "asientoId": a.id, "numero": a.numero,
                         "fecha": a.fecha.isoformat(), "concepto": a.concepto, "detalle": l.detalle,
                         "importe": _f(l.debe - l.haber), "conciliada": l.id in conciliadas}
                        for l, a in movimientos],
        "totales": {"saldoExtracto": _f(saldo_extracto), "saldoMayor": _f(saldo_mayor),
                    "diferencia": _f(saldo_extracto - saldo_mayor),
                    "pendienteExtracto": _f(pend_ext), "pendienteMayor": _f(pend_may),
                    "conciliadas": len(conciliadas)},
    }


def conciliar(db: Session, extracto_id: int, asiento_linea_id: int, usuario: str) -> dict:
    e = db.get(models.LineaExtracto, extracto_id)
    if e is None:
        raise ErrorContable("La línea del extracto no existe.")
    if e.asiento_linea_id:
        raise ErrorContable("Esa línea del extracto ya está conciliada.")
    linea = db.get(models.AsientoLinea, asiento_linea_id)
    if linea is None or linea.cuenta_codigo != e.cuenta_codigo:
        raise ErrorContable("El movimiento no es de esta cuenta.")
    ya = db.scalar(select(models.LineaExtracto).where(models.LineaExtracto.asiento_linea_id == asiento_linea_id))
    if ya:
        raise ErrorContable("Ese movimiento del mayor ya está conciliado con otra línea del extracto.")
    if (linea.debe - linea.haber) != e.importe:
        raise ErrorContable(f"Los importes no coinciden: extracto {e.importe} ≠ mayor {linea.debe - linea.haber}.")
    e.asiento_linea_id = asiento_linea_id
    e.conciliada_por = usuario
    e.conciliada_en = datetime.now()
    db.commit()
    return {"conciliada": True, "extractoId": e.id, "asientoLineaId": asiento_linea_id}


def desconciliar(db: Session, extracto_id: int) -> dict:
    e = db.get(models.LineaExtracto, extracto_id)
    if e is None:
        raise ErrorContable("La línea del extracto no existe.")
    e.asiento_linea_id, e.conciliada_por, e.conciliada_en = None, "", None
    db.commit()
    return {"conciliada": False, "extractoId": e.id}


def automatica(db: Session, cuenta_codigo: str, usuario: str) -> dict:
    """Empareja lo que queda pendiente por importe y fecha (misma fecha primero, después ±5 días)."""
    datos = estado(db, cuenta_codigo)
    pendientes_ext = [e for e in datos["extracto"] if not e["conciliada"]]
    pendientes_mov = [m for m in datos["movimientos"] if not m["conciliada"]]
    usados, conciliadas = set(), 0
    for tolerancia in (0, 5):
        for e in pendientes_ext:
            if e["conciliada"]:
                continue
            for m in pendientes_mov:
                if m["asientoLineaId"] in usados or m["importe"] != e["importe"]:
                    continue
                dias = abs((date.fromisoformat(e["fecha"]) - date.fromisoformat(m["fecha"])).days)
                if dias > tolerancia:
                    continue
                conciliar(db, e["id"], m["asientoLineaId"], usuario)
                usados.add(m["asientoLineaId"])
                e["conciliada"] = True
                conciliadas += 1
                break
    return {"conciliadas": conciliadas, **estado(db, cuenta_codigo)["totales"]}
