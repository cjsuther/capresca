"""Caja del circuito de créditos: pendientes de cobro y cancelación anticipada con su recibo.

La cobranza de ventanilla de CCyPP no se migró (los contratos se cobran por el servicing).
La mora usa `domain.mora.calcular_mora`, validado contra ivacob.DBF.
Base del punitorio (según `recalculo` del VFP):
    base = amortizacion + interes + iva_interes - total_pagado
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.domain.mora import calcular_mora, ResultadoMora
from app import models

CERO = Decimal("0.00")


class ReglaNegocioError(Exception):
    pass


def _linea_de_credito(db: Session, credito: models.Credito) -> models.LineaCredito:
    # Preferir linea_id (denormalizado, presente en créditos del ETL); si no,
    # resolver vía la solicitud (créditos otorgados por la app).
    if credito.linea_id:
        return db.get(models.LineaCredito, credito.linea_id)
    if credito.solicitud_id:
        sol = db.get(models.Solicitud, credito.solicitud_id)
        if sol:
            return db.get(models.LineaCredito, sol.linea_id)
    return None


def _mora_de_cuota(cuota: models.Cuota, linea: models.LineaCredito,
                   fecha_pago: date) -> ResultadoMora:
    dias = (fecha_pago - cuota.fecha_vencimiento).days
    if dias <= 0:
        return calcular_mora(CERO, CERO, 0, CERO)
    base = cuota.amortizacion + cuota.interes + cuota.iva_interes - cuota.total_pagado
    return calcular_mora(
        cuota=base,
        saldo=cuota.saldo_capital,
        dias=dias,
        tasa_punitoria_diaria=linea.tasa_mora_diaria,
        tasa_resarcitoria_diaria=CERO,       # confirmado 0 en producción (ivacob)
        tasa_iva=linea.iva,
    )


def _proximo_numero_recibo(db: Session) -> int:
    ultimo = db.scalar(select(func.max(models.Recibo.numero))) or 0
    return ultimo + 1


def _emitir_recibo(db: Session, **campos) -> models.Recibo:
    """Crea un Recibo con número único, reintentando ante la carrera de otro cajero (primer-libre +
    SAVEPOINT; la constraint única de la DB es el árbitro). Evita el TOCTOU de dos recibos con el mismo número."""
    from app.core.numbering import crear_con_numero_unico

    def _construir(n):
        r = models.Recibo(numero=n, **campos)
        db.add(r)
        return r
    return crear_con_numero_unico(db, lambda: _proximo_numero_recibo(db), _construir)


def pendientes_cobro(db: Session, fecha_corte: date, solo_vencidas: bool = True) -> dict:
    """Cuotas impagas de créditos activos a una fecha de corte, con mora.

    Informe VFP: frm230050000rptpend (Emisión de Pendientes/Ingresos).
    """
    q = (
        select(models.Cuota, models.Credito, models.Cliente)
        .join(models.Credito, models.Credito.id == models.Cuota.credito_id)
        .join(models.Cliente, models.Cliente.id == models.Credito.cliente_id)
        .where(models.Cuota.estado != "P", models.Credito.estado == "A")
        .order_by(models.Cliente.apellido_nombre, models.Cuota.fecha_vencimiento)
    )
    if solo_vencidas:
        q = q.where(models.Cuota.fecha_vencimiento <= fecha_corte)

    lineas_cache: dict[int, models.LineaCredito] = {}
    items = []
    total_cuota = total_mora = CERO
    for cuota, credito, cliente in db.execute(q).all():
        if credito.id not in lineas_cache:
            lineas_cache[credito.id] = _linea_de_credito(db, credito)
        m = _mora_de_cuota(cuota, lineas_cache[credito.id], fecha_corte)
        pendiente = cuota.total - cuota.total_pagado
        mora = m.interes_punitorio + m.iva_punitorio
        items.append({
            "credito_id": credito.id, "cliente": cliente.apellido_nombre,
            "cuil": cliente.cuil, "cuota_numero": cuota.numero,
            "vencimiento": cuota.fecha_vencimiento, "dias_mora": m.dias,
            "importe_cuota": pendiente, "mora": mora,
            "total": pendiente + mora,
        })
        total_cuota += pendiente
        total_mora += mora
    return {"fecha_corte": fecha_corte, "cantidad": len(items),
            "total_cuota": total_cuota, "total_mora": total_mora,
            "total": total_cuota + total_mora, "items": items}


def _detalle_cancelacion(db: Session, credito: models.Credito, fecha: date) -> dict:
    """Detalle del pago para cancelar anticipadamente un crédito (VFP: cancela_
    anticipada / osets.cancelacre). Las cuotas **vencidas** se pagan completas
    (capital+interés+IVA) con su **mora**; las cuotas **futuras** pagan sólo el
    **capital** (se condona el interés/IVA no devengado — beneficio del pago
    anticipado)."""
    linea = _linea_de_credito(db, credito)
    cuotas = db.scalars(select(models.Cuota).where(
        models.Cuota.credito_id == credito.id,
        models.Cuota.estado != "P").order_by(models.Cuota.numero)).all()
    items = []
    cap = interes = iva = punit = ivapun = CERO
    for c in cuotas:
        vencida = c.fecha_vencimiento <= fecha
        pendiente = c.total - c.total_pagado
        if vencida:
            m = _mora_de_cuota(c, linea, fecha)
            sub = pendiente + m.interes_punitorio + m.iva_punitorio
            cap += c.amortizacion; interes += c.interes; iva += c.iva_interes
            punit += m.interes_punitorio; ivapun += m.iva_punitorio
            items.append({"cuota": c.numero, "vencida": True, "capital": c.amortizacion,
                          "interes": c.interes, "iva": c.iva_interes,
                          "punitorio": m.interes_punitorio, "iva_punit": m.iva_punitorio,
                          "subtotal": sub})
        else:  # futura: sólo capital, se condona interés/IVA no devengado
            cap += c.amortizacion
            items.append({"cuota": c.numero, "vencida": False, "capital": c.amortizacion,
                          "interes": CERO, "iva": CERO, "punitorio": CERO,
                          "iva_punit": CERO, "subtotal": c.amortizacion})
    total = cap + interes + iva + punit + ivapun
    return {"credito_id": credito.id, "cantidad_cuotas": len(items),
            "capital": cap, "interes": interes, "iva": iva,
            "punitorio": punit, "iva_punit": ivapun, "total": total, "items": items}


def simular_cancelacion(db: Session, credito_id: int, fecha: date) -> dict:
    """Cuánto hay que pagar para cancelar anticipadamente un crédito (sin cobrar)."""
    credito = db.get(models.Credito, credito_id)
    if not credito:
        raise ReglaNegocioError("Crédito inexistente")
    if credito.estado == "C":
        raise ReglaNegocioError("El crédito ya está cancelado")
    return _detalle_cancelacion(db, credito, fecha)


def cancelar_credito(db: Session, *, credito_id: int, fecha_pago: date,
                     via_pago: str, cajero: str) -> models.Recibo:
    """Cancelación anticipada de un crédito por caja (VFP: frm320450000cancre,
    cancela_anticipada). Emite un recibo por el total a cancelar, salda TODAS las
    cuotas pendientes, pone saldo_capital=0 y el crédito en estado C."""
    credito = db.get(models.Credito, credito_id)
    if not credito:
        raise ReglaNegocioError("Crédito inexistente")
    if credito.estado == "C":
        raise ReglaNegocioError("El crédito ya está cancelado")
    det = _detalle_cancelacion(db, credito, fecha_pago)
    if det["cantidad_cuotas"] == 0:
        raise ReglaNegocioError("El crédito no tiene cuotas pendientes")

    recibo = _emitir_recibo(
        db, fecha_pago=fecha_pago, cliente_id=credito.cliente_id, credito_id=credito.id,
        cajero=cajero, via_pago=via_pago, estado="E", total=det["total"])

    cuotas = db.scalars(select(models.Cuota).where(
        models.Cuota.credito_id == credito.id,
        models.Cuota.estado != "P").order_by(models.Cuota.numero)).all()
    linea = _linea_de_credito(db, credito)
    for c in cuotas:
        vencida = c.fecha_vencimiento <= fecha_pago
        if vencida:
            m = _mora_de_cuota(c, linea, fecha_pago)
            ipun, ivapun, inte, ivai = (m.interes_punitorio, m.iva_punitorio,
                                        c.interes, c.iva_interes)
        else:
            ipun = ivapun = inte = ivai = CERO
        pagado = c.amortizacion + inte + ivai + ipun + ivapun
        db.add(models.PagoCuota(
            recibo_id=recibo.id, cuota_id=c.id, capital=c.amortizacion,
            interes=inte, iva_interes=ivai, seguro=CERO, gastos_adm=CERO,
            interes_punitorio=ipun, iva_punitorio=ivapun,
            dias_mora=(fecha_pago - c.fecha_vencimiento).days if vencida else 0,
            total_pagado=pagado))
        c.total_pagado = c.total
        c.estado = "P"
        c.fecha_pago = fecha_pago
        c.nro_recibo = recibo.numero
        c.via_pago = via_pago
        c.usuario_pago = cajero
    credito.saldo_capital = CERO
    credito.estado = "C"

    from app.services import contabilidad
    contabilidad.asiento_cobranza(db, recibo)
    db.commit()
    db.refresh(recibo)
    return recibo
