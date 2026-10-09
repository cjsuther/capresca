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


# ----------------------- OP por lote de desembolsos (Tesorería → Interbanking) -----------------------
# El circuito actual no gira un cheque por crédito: la liquidación arma un lote, Tesorería lo aprueba y lo
# manda por Interbanking. La OP es una por lote, se emite ANTES de mandarlo (su número viaja en la
# descripción del lote de Tesorería) y queda girada cuando todos sus pagos tienen resultado.

def op_lote_desembolsos(db: Session, *, referencia: str, contratos: list, importe: Decimal,
                        resoluciones: str, concepto: str) -> models.OrdenPago:
    """La OP de un envío a Tesorería. Reintentar el mismo envío (misma referencia) reusa la OP."""
    op = db.query(models.OrdenPago).filter_by(referencia=referencia, tipo="CREDITO").first()
    if op is None:
        op = crear_op(db, beneficiario="Varios (lote de desembolsos)", concepto=concepto[:120],
                      importe=importe, tipo="CREDITO", commit=False)
        op.referencia = referencia
    if op.estado == "P":
        op.importe, op.contratos, op.resoluciones = Decimal(str(importe)), list(contratos), resoluciones[:200]
        op.medio_pago, op.banco = "TRANSFERENCIA", "INTERBANKING"
    return op


def op_de_lote(db: Session, lote: str) -> models.OrdenPago | None:
    return db.query(models.OrdenPago).filter_by(lote_tesoreria=lote, tipo="CREDITO").first() if lote else None


def cerrar_op_si_termino(db: Session, op: models.OrdenPago, desembolsos: dict[str, dict]) -> None:
    """Con el resultado de cada contrato ({id: datos_adicionales.desembolso}): mientras alguno siga en
    Tesorería, la OP queda pendiente; si no, se gira por lo acreditado, o se anula si no salió nada."""
    if op.estado != "P":
        return
    pagado, pendiente = Decimal(0), False
    for cid, d in desembolsos.items():
        if d.get("lote") != op.lote_tesoreria:
            continue                                  # volvió a liquidarse en otro lote: no es de esta OP
        if d.get("estado") == "EN_TESORERIA":
            pendiente = True
        elif d.get("estado") == "CONFIRMADO":
            pagado += Decimal(str(d.get("monto") or 0))
    op.importe_pagado = pagado
    if pendiente:
        return
    op.estado = "G" if pagado > 0 else "A"
    op.fecha_pago = date.today()
