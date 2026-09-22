"""Orden de pago del desembolso de un crédito (VFP: agjsegresos / maeop).

La tesorería de CCyPP (chequeras, pagos a aseguradoras y proveedores) no se migró a Portezuelo; queda
sólo la OP que genera el otorgamiento, con su numeración correlativa.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import models


class ReglaNegocioError(Exception):
    pass


def _proximo_numero(db: Session) -> int:
    return (db.scalar(select(func.max(models.OrdenPago.numero))) or 0) + 1


_ESTADOS = {"P": "pendiente", "G": "girado", "A": "anulado"}


def crear_op(db: Session, *, beneficiario: str, concepto: str, importe: Decimal,
             tipo: str = "PROVEEDOR", cuit: str = "", fecha: date | None = None,
             credito_id: int | None = None, commit: bool = True) -> models.OrdenPago:
    from app.core.numbering import crear_con_numero_unico

    def _construir(n):
        o = models.OrdenPago(
            numero=n, fecha=fecha or date.today(),
            beneficiario=beneficiario, cuit_beneficiario=cuit, concepto=concepto,
            tipo=tipo, importe=Decimal(importe), estado="P", credito_id=credito_id,
        )
        db.add(o)
        return o
    op = crear_con_numero_unico(db, lambda: _proximo_numero(db), _construir)   # árbitro DB (H-108)
    if commit:
        db.commit()
        db.refresh(op)
    else:
        db.flush()
    return op


def op_desembolso_credito(db: Session, credito: models.Credito,
                          beneficiario: str) -> models.OrdenPago:
    """OP pendiente por el desembolso de un crédito recién otorgado."""
    return crear_op(
        db, beneficiario=beneficiario,
        concepto=f"Desembolso crédito N° {credito.id}", importe=credito.capital,
        tipo="CREDITO", fecha=credito.fecha_otorgamiento or date.today(),
        credito_id=credito.id, commit=False,
    )
