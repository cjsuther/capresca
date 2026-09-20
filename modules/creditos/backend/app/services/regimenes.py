"""Servicios de regímenes especiales de seguros (Malvinas, subsidios, etc.).

Genera las cuotas mensuales de los beneficiarios vigentes y, para regímenes de
pago, emite la orden de pago en Tesorería (VFP: 'Generar Cuotas Tesorería').
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services import egresos
from app import models

CERO = Decimal("0.00")
_PERIODO_RE = re.compile(r"^\d{4}-\d{2}$")


class ReglaNegocioError(Exception):
    pass


def crear_beneficiario(db: Session, *, regimen_id: int, apellido_nombre: str,
                       cuil: str = "", dni: str = "", cbu: str = "",
                       monto_mensual: Decimal | None = None,
                       numero_resolucion: str = "",
                       fecha_alta: date | None = None) -> models.Beneficiario:
    reg = db.get(models.RegimenEspecial, regimen_id)
    if not reg or not reg.activo:
        raise ReglaNegocioError("Régimen inexistente o inactivo")
    monto = monto_mensual if monto_mensual is not None else reg.monto_default
    b = models.Beneficiario(
        regimen_id=regimen_id, apellido_nombre=apellido_nombre, cuil=cuil, dni=dni,
        cbu=cbu, monto_mensual=Decimal(monto), numero_resolucion=numero_resolucion,
        fecha_alta=fecha_alta or date.today(), estado="V",
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def dar_de_baja(db: Session, beneficiario_id: int) -> models.Beneficiario:
    b = db.get(models.Beneficiario, beneficiario_id)
    if not b:
        raise ReglaNegocioError("Beneficiario inexistente")
    b.estado = "B"
    db.commit()
    db.refresh(b)
    return b


def generar_cuotas(db: Session, regimen_id: int, periodo: str) -> dict:
    """Genera las cuotas del período para los beneficiarios vigentes.

    Para regímenes de pago (tipo=P) emite además la OP en Tesorería.
    Idempotente: no duplica cuotas ya generadas para ese período.
    """
    if not _PERIODO_RE.match(periodo):
        raise ReglaNegocioError("Período inválido (formato YYYY-MM)")
    reg = db.get(models.RegimenEspecial, regimen_id)
    if not reg:
        raise ReglaNegocioError("Régimen inexistente")

    beneficiarios = db.scalars(select(models.Beneficiario).where(
        models.Beneficiario.regimen_id == regimen_id,
        models.Beneficiario.estado == "V")).all()

    generadas = 0
    total = CERO
    ops = 0
    fecha = date(int(periodo[:4]), int(periodo[5:7]), 1)
    for b in beneficiarios:
        ya = db.scalar(select(models.CuotaRegimen).where(
            models.CuotaRegimen.beneficiario_id == b.id,
            models.CuotaRegimen.periodo == periodo))
        if ya:
            continue
        cuota = models.CuotaRegimen(
            beneficiario_id=b.id, regimen_id=regimen_id, periodo=periodo,
            monto=b.monto_mensual, estado="G",
        )
        db.add(cuota)
        db.flush()
        if reg.tipo == "P" and b.monto_mensual > 0:
            op = egresos.crear_op(
                db, beneficiario=b.apellido_nombre,
                concepto=f"{reg.nombre} — período {periodo}",
                importe=b.monto_mensual, tipo="SEGURO", cuit=b.cuil,
                fecha=fecha, commit=False)
            cuota.orden_pago_id = op.id
            cuota.estado = "L"
            ops += 1
        generadas += 1
        total += b.monto_mensual

    db.commit()
    return {"regimen": reg.nombre, "periodo": periodo, "cuotas_generadas": generadas,
            "ordenes_pago": ops, "total": total,
            "beneficiarios_vigentes": len(beneficiarios)}
