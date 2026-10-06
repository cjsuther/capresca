"""Lotes de liquidación: dónde queda cada contrato originado A_LIQUIDAR.

Un lote junta contratos del mismo producto (tipo de crédito) originados el mismo día, hasta el tope
del parámetro LOTE_LIQUIDACION_MAX (Créditos → Parámetros; 50 si no está cargado). El número es
correlativo dentro del año y arranca en 1 cada año: 2026-0001, 2026-0002…

El lote se fija al originar y no cambia: el contrato entra al último lote de su producto y día, y si
ese ya está lleno se abre el siguiente. El lote se toma con lock antes de contarlo, así dos
originaciones simultáneas no lo pasan del tope. Abrir un lote lo arbitra la DB con dos constraints
únicas: (anio, numero), para que el número no se repita, y (producto, fecha, orden), para que dos
originaciones simultáneas no abran dos lotes a la vez; la que choca reintenta y entra al que abrió
la otra.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, models_productos as m

PARAMETRO = "LOTE_LIQUIDACION_MAX"
POR_DEFECTO = 50


def maximo(db: Session) -> int:
    p = db.query(models.Parametro).filter(models.Parametro.clave == PARAMETRO).first()
    try:
        return max(1, int(str(p.valor).strip())) if p else POR_DEFECTO
    except ValueError:
        return POR_DEFECTO


def _proximo_numero(db: Session, anio: int) -> int:
    ultimo = db.query(func.max(m.PPLoteLiquidacion.numero)).filter(m.PPLoteLiquidacion.anio == anio).scalar()
    return (ultimo or 0) + 1


def asignar(db: Session, c: m.PPContrato, tope: int | None = None, intentos: int = 10) -> m.PPLoteLiquidacion:
    """Ubica el contrato en su lote (no hace commit). Si ya tiene uno, no lo cambia."""
    if c.lote_liquidacion_id:
        return db.get(m.PPLoteLiquidacion, c.lote_liquidacion_id)
    tope = tope or maximo(db)
    ultimo_error: IntegrityError | None = None
    for _ in range(max(1, intentos)):
        abierto = (db.query(m.PPLoteLiquidacion)
                   .filter(m.PPLoteLiquidacion.producto_id == c.producto_id,
                           m.PPLoteLiquidacion.fecha == c.fecha_valor)
                   .order_by(m.PPLoteLiquidacion.orden.desc()).with_for_update().first())
        if abierto is not None:
            ocupados = db.query(func.count(m.PPContrato.id)).filter(
                m.PPContrato.lote_liquidacion_id == abierto.id).scalar()
            if ocupados < tope:
                c.lote_liquidacion_id = abierto.id
                db.flush()
                return abierto
        anio = c.fecha_valor.year
        try:
            with db.begin_nested():
                lote = m.PPLoteLiquidacion(anio=anio, numero=_proximo_numero(db, anio), producto_id=c.producto_id,
                                           fecha=c.fecha_valor, orden=(abierto.orden + 1) if abierto else 1)
                db.add(lote)
                db.flush()
        except IntegrityError as e:     # otro abrió ese lote o tomó ese número → releer y reintentar
            ultimo_error = e
            continue
        c.lote_liquidacion_id = lote.id
        db.flush()
        return lote
    assert ultimo_error is not None
    raise ultimo_error


def asignar_pendientes(db: Session) -> int:
    """Ubica en lotes los A_LIQUIDAR que no tienen (los originados antes de los lotes numerados)."""
    sueltos = (db.query(m.PPContrato)
               .filter(m.PPContrato.estado == "A_LIQUIDAR", m.PPContrato.lote_liquidacion_id.is_(None))
               .order_by(m.PPContrato.fecha_valor, m.PPContrato.numero_contrato).all())
    if not sueltos:
        return 0
    tope = maximo(db)
    for c in sueltos:
        asignar(db, c, tope)
    db.commit()
    return len(sueltos)
