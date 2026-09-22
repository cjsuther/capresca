"""Servicios de créditos a jubilados / Ley 5094 (VFP: sol_jubi, jub_ctas)."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import models

CERO = Decimal("0.00")


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
