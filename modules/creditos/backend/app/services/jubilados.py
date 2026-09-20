"""Servicios de créditos a jubilados / Ley 5094 (VFP: sol_jubi, jub_ctas)."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import models

CERO = Decimal("0.00")


def listar(db: Session, liquidada: bool | None = None, limit: int = 200) -> list[dict]:
    q = select(models.CreditoJubilado)
    if liquidada is not None:
        q = q.where(models.CreditoJubilado.liquidada == liquidada)
    q = q.order_by(models.CreditoJubilado.id.desc()).limit(limit)
    return [{"id": c.id, "beneficiario_nro": c.beneficiario_nro, "cuil": c.cuil,
             "apellido_nombre": c.apellido_nombre, "localidad": c.localidad,
             "departamento": c.departamento, "monto": c.monto,
             "cantidad_cuotas": c.cantidad_cuotas, "liquidada": c.liquidada,
             "prorroga": c.prorroga} for c in db.scalars(q).all()]


def cuotas(db: Session, credito_jubilado_id: int) -> list[dict]:
    cs = db.scalars(select(models.CuotaJubilado).where(
        models.CuotaJubilado.credito_jubilado_id == credito_jubilado_id)
        .order_by(models.CuotaJubilado.numero)).all()
    return [{"numero": c.numero, "valor": c.valor, "fecha_vencimiento": c.fecha_vencimiento,
             "pagada": c.pagada, "fecha_pago": c.fecha_pago, "no_op": c.no_op}
            for c in cs]


def por_departamento(db: Session) -> list[dict]:
    """Créditos Ley 5094 agrupados por departamento (VFP: frm330251000soljubdpto)."""
    q = (select(models.CreditoJubilado.departamento,
                func.count(models.CreditoJubilado.id),
                func.coalesce(func.sum(models.CreditoJubilado.monto), 0))
         .group_by(models.CreditoJubilado.departamento))
    out = []
    for dep, n, monto in db.execute(q).all():
        out.append({"departamento": dep or "(sin depto)", "cantidad": n,
                    "monto_total": Decimal(monto)})
    return sorted(out, key=lambda x: -x["cantidad"])


def resumen(db: Session) -> dict:
    total = db.scalar(select(func.count()).select_from(models.CreditoJubilado)) or 0
    liq = db.scalar(select(func.count()).select_from(models.CreditoJubilado)
                    .where(models.CreditoJubilado.liquidada.is_(True))) or 0
    monto = db.scalar(select(func.coalesce(func.sum(models.CreditoJubilado.monto), 0))) or 0
    return {"total": total, "liquidadas": liq, "pendientes": total - liq,
            "monto_total": Decimal(monto)}
