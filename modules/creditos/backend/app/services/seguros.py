"""Póliza del seguro de vida que se emite al otorgar un crédito.

El seguro se cobra por cuota (columna `seguro` de la cuota/pago). La liquidación a la aseguradora
(VFP: liqsegur / cajacreseg) era del área Seguros de CCyPP, que no se migró a Portezuelo.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import models

CERO = Decimal("0.00")

# Tipos de seguro de vida colectivo (VFP: Seguros/paraseguros.dbf, CODIGO).
TIPOS_SEGURO = {
    1: "Subsidio de Protección a la Familia",
    2: "Seguro de Sepelio",
    3: "Seguro de Vida Obligatorio",
    4: "Seguro de Incapacidad",
    5: "Seguro de Vida Adicional",
}


def _proximo_numero_poliza(db: Session) -> int:
    return (db.scalar(select(func.max(models.Poliza.numero))) or 0) + 1


def crear_poliza_si_corresponde(db: Session, credito: models.Credito,
                                linea: models.LineaCredito) -> models.Poliza | None:
    """Si la línea tiene compañía y prima de seguro, emite la póliza del crédito."""
    if not linea.compania_seguros_id or linea.seguro_pct <= 0:
        return None
    from app.core.numbering import crear_con_numero_unico

    def _construir(n):
        p = models.Poliza(
            numero=n, credito_id=credito.id, cliente_id=credito.cliente_id,
            compania_id=linea.compania_seguros_id, capital_asegurado=credito.capital,
            fecha_alta=credito.fecha_otorgamiento or date.today(), estado="V",
        )
        db.add(p)
        return p
    return crear_con_numero_unico(db, lambda: _proximo_numero_poliza(db), _construir)  # árbitro DB (H-108)
