"""Consultas e informes del módulo Créditos (read-only).

Reemplazan pantallas VFP como: Informe Situación de un Cliente
(frm315650000hiscre), Consulta situación de Margen (frm315400000sitmar),
Estadísticas (frm315350000estadvar) y Consulta de envíos de cuotas
(frm315300000consenvios).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.services.creditos import total_afectado
from app.domain.margen import margen_disponible
from app.domain import carteras
from app import models

CERO = Decimal("0.00")


def situacion_cliente(db: Session, cliente_id: int) -> dict | None:
    cliente = db.get(models.Cliente, cliente_id)
    if not cliente:
        return None

    creditos = db.scalars(select(models.Credito).where(
        models.Credito.cliente_id == cliente_id)).all()

    resumenes = []
    saldo_total = CERO
    activos = 0
    for cr in creditos:
        linea = db.get(models.LineaCredito, cr.linea_id) if cr.linea_id else None
        pend = db.scalars(select(models.Cuota).where(
            models.Cuota.credito_id == cr.id,
            models.Cuota.estado != "P").order_by(models.Cuota.numero)).all()
        prox = pend[0] if pend else None
        if cr.estado == "A":
            activos += 1
            saldo_total += cr.saldo_capital
        resumenes.append({
            "id": cr.id, "capital": cr.capital, "saldo_capital": cr.saldo_capital,
            "estado": cr.estado, "linea": linea.nombre if linea else "",
            "cuotas_pendientes": len(pend),
            "proxima_cuota_vto": prox.fecha_vencimiento if prox else None,
            "proxima_cuota_importe": prox.total if prox else None,
        })

    afectado = total_afectado(db, cliente_id)
    # margen usa el por_afecta de la última línea operada (aprox.)
    por_afecta = None
    margen = None
    if creditos:
        ult = creditos[-1]
        linea = db.get(models.LineaCredito, ult.linea_id) if ult.linea_id else None
        if linea:
            por_afecta = linea.por_afecta
            margen = margen_disponible(cliente.sueldo, linea.por_afecta, afectado).margen_disponible

    return {
        "cliente_id": cliente.id, "apellido_nombre": cliente.apellido_nombre,
        "cuil": cliente.cuil, "sueldo": cliente.sueldo, "cbu": cliente.cbu,
        "por_afecta": por_afecta, "total_afectado": afectado,
        "margen_disponible": margen, "creditos_activos": activos,
        "saldo_total": saldo_total, "creditos": resumenes,
    }


def estadisticas_cartera(db: Session) -> dict:
    activos = db.scalar(select(func.count()).select_from(models.Credito).where(
        models.Credito.estado == "A")) or 0
    cancelados = db.scalar(select(func.count()).select_from(models.Credito).where(
        models.Credito.estado == "C")) or 0
    capital_total = db.scalar(select(func.coalesce(func.sum(models.Credito.capital), 0))) or 0
    saldo_total = db.scalar(select(func.coalesce(func.sum(models.Credito.saldo_capital), 0)).where(
        models.Credito.estado == "A")) or 0

    # por línea (join crédito -> solicitud -> línea)
    q = (
        select(models.LineaCredito.id, models.LineaCredito.nombre,
               models.LineaCredito.cartera,
               func.count(models.Credito.id),
               func.coalesce(func.sum(models.Credito.capital), 0),
               func.coalesce(func.sum(models.Credito.saldo_capital), 0))
        .join(models.Credito, models.Credito.linea_id == models.LineaCredito.id)
        .group_by(models.LineaCredito.id, models.LineaCredito.nombre,
                  models.LineaCredito.cartera)
    )
    por_linea = [
        {"linea_id": lid, "linea": nom, "cartera": cart, "cantidad": cant,
         "capital_otorgado": Decimal(cap), "saldo": Decimal(sal)}
        for lid, nom, cart, cant, cap, sal in db.execute(q).all()
    ]
    return {
        "creditos_activos": activos, "creditos_cancelados": cancelados,
        "capital_otorgado_total": Decimal(capital_total),
        "saldo_total": Decimal(saldo_total), "por_linea": por_linea,
    }


_LISTADO_COLS = {
    "credito_id": models.Credito.id,
    "capital": models.Credito.capital,
    "saldo": models.Credito.saldo_capital,
    "fecha_otorgamiento": models.Credito.fecha_otorgamiento,
    "cliente": models.Cliente.apellido_nombre,
}


def listado_creditos(db: Session, estado: str | None = None, *, q: str | None = None,
                     linea_id: int | None = None, cartera: int | None = None,
                     organismo_id: int | None = None, desde=None, hasta=None,
                     con_saldo: bool | None = None,
                     limit: int = 25, offset: int = 0,
                     sort: str = "credito_id", order: str = "desc",
                     cap: int = 200) -> dict:
    """Listado/informe paginado de créditos con filtros combinables (VFP: 330 /
    33085 "Informes varios": estado, saldos, por línea/cartera/organismo, cancelados…).

    `total_capital`/`total_saldo` son del set filtrado completo, no de la página."""
    base = (
        select(models.Credito, models.Cliente, models.LineaCredito)
        .join(models.Cliente, models.Cliente.id == models.Credito.cliente_id)
        .outerjoin(models.LineaCredito, models.LineaCredito.id == models.Credito.linea_id)
    )
    if estado:
        base = base.where(models.Credito.estado == estado)
    if linea_id:
        base = base.where(models.Credito.linea_id == linea_id)
    if cartera is not None:
        base = base.where(models.LineaCredito.cartera == cartera)
    if organismo_id:
        base = base.where(models.Cliente.organismo_id == organismo_id)
    if desde:
        base = base.where(models.Credito.fecha_otorgamiento >= desde)
    if hasta:
        base = base.where(models.Credito.fecha_otorgamiento <= hasta)
    if con_saldo is True:
        base = base.where(models.Credito.saldo_capital > 0)
    elif con_saldo is False:
        base = base.where(models.Credito.saldo_capital <= 0)
    if q:
        like = f"%{q.upper()}%"
        base = base.where(models.Cliente.apellido_nombre.like(like)
                          | models.Cliente.cuil.like(like))

    # Totales del set completo (una sola consulta agregada).
    tot_q = base.with_only_columns(
        func.count(models.Credito.id),
        func.coalesce(func.sum(models.Credito.capital), 0),
        func.coalesce(func.sum(models.Credito.saldo_capital), 0),
    ).order_by(None)
    total, total_capital, total_saldo = db.execute(tot_q).one()

    col = _LISTADO_COLS.get(sort, models.Credito.id)
    base = base.order_by(col.desc() if order == "desc" else col.asc())
    base = base.limit(min(limit, cap)).offset(max(offset, 0))

    items = [{"credito_id": cr.id, "cliente": cli.apellido_nombre,
              "cuil": cli.cuil, "linea": lin.nombre if lin else "—",
              "capital": cr.capital, "saldo": cr.saldo_capital, "estado": cr.estado,
              "fecha_otorgamiento": cr.fecha_otorgamiento}
             for cr, cli, lin in db.execute(base).all()]
    return {"total": total, "limit": limit, "offset": offset,
            "cantidad": total, "total_capital": Decimal(total_capital),
            "total_saldo": Decimal(total_saldo), "items": items}


def turnos_otorgados(db: Session, *, periodo: str | None = None, tipo: str | None = None,
                     usado: bool | None = None, q: str | None = None,
                     limit: int = 25, offset: int = 0, cap: int = 200) -> dict:
    """Turnos otorgados para solicitar crédito, paginado (VFP: 31560).

    Selecciona columnas puntuales (no el objeto ORM) para exportar rápido."""
    T = models.TurnoCredito
    cols = (T.tipo, T.numero, T.periodo, T.fecha, T.cuil, T.apellido_nombre,
            T.linea, T.sueldo, T.usado, T.autorizado)
    base = select(*cols)
    if periodo:
        base = base.where(T.periodo == periodo)
    if tipo:
        base = base.where(T.tipo == tipo)
    if usado is not None:
        base = base.where(T.usado.is_(usado))
    if q:
        like = f"%{q.upper()}%"
        base = base.where(T.apellido_nombre.like(like) | T.cuil.like(like))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(base.order_by(T.fecha.desc(), T.numero.desc())
                      .limit(min(limit, cap)).offset(max(offset, 0))).all()
    items = [{"tipo": r.tipo, "numero": r.numero, "periodo": r.periodo,
              "fecha": r.fecha, "cuil": r.cuil, "apellido_nombre": r.apellido_nombre,
              "linea": r.linea, "sueldo": r.sueldo, "usado": r.usado,
              "autorizado": r.autorizado} for r in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def situacion_por_cartera(db: Session) -> dict:
    """Cantidades y situación de créditos agrupados por cartera (VFP: 31537).

    Cada línea pertenece a una cartera; se agregan activos/cancelados y saldo."""
    # saldo negativo = dato corrupto del backup (nsdonor); se clampa a 0 para no
    # distorsionar los totales de cartera. Ver H-023. (case es portable SQLite/PG)
    saldo_ok = case((models.Credito.saldo_capital < 0, 0), else_=models.Credito.saldo_capital)
    capital_ok = case((models.Credito.capital < 0, 0), else_=models.Credito.capital)
    q = (
        select(models.LineaCredito.cartera, models.Credito.estado,
               func.count(models.Credito.id),
               func.coalesce(func.sum(capital_ok), 0),
               func.coalesce(func.sum(saldo_ok), 0))
        .join(models.Credito, models.Credito.linea_id == models.LineaCredito.id)
        .group_by(models.LineaCredito.cartera, models.Credito.estado)
    )
    anomalias = db.scalar(select(func.count()).select_from(models.Credito)
                          .where(models.Credito.saldo_capital < 0)) or 0
    por_cartera: dict[int, dict] = {}
    tot = {"activos": 0, "cancelados": 0, "capital": Decimal("0"), "saldo": Decimal("0")}
    for cartera, estado, n, cap, sal in db.execute(q).all():
        cap, sal = Decimal(cap), Decimal(sal)
        fila = por_cartera.setdefault(cartera or 0, {
            "cartera": cartera or 0,
            "nombre": carteras.CARTERA_NOMBRE.get(cartera, f"Cartera {cartera or '—'}"),
            "activos": 0, "cancelados": 0, "capital": Decimal("0"), "saldo": Decimal("0")})
        if estado == "A":
            fila["activos"] += n; fila["saldo"] += sal; tot["activos"] += n; tot["saldo"] += sal
        elif estado == "C":
            fila["cancelados"] += n; tot["cancelados"] += n
        fila["capital"] += cap; tot["capital"] += cap
    filas = sorted(por_cartera.values(), key=lambda f: f["saldo"], reverse=True)
    return {"por_cartera": filas, "total": tot, "anomalias_saldo_negativo": anomalias}


def pagos_en_caja(db: Session, *, desde: date | None = None, hasta: date | None = None,
                  credito_id: int | None = None, via: str | None = None,
                  limit: int = 25, offset: int = 0, cap: int = 200) -> dict:
    """Pagos de cuotas registrados en caja (VFP: frm315550000pagcrecaja).

    Usa los datos de pago reales de la cuota (fecha_pago, recibo, vía, cajero)."""
    C = models.Cuota
    # Se seleccionan sólo las columnas necesarias (no los objetos ORM completos):
    # es mucho más rápido al exportar decenas de miles de filas.
    base = (select(C.credito_id, C.numero, models.Cliente.apellido_nombre,
                   C.fecha_pago, C.nro_recibo, C.via_pago, C.usuario_pago, C.total_pagado)
            .join(models.Credito, models.Credito.id == C.credito_id)
            .join(models.Cliente, models.Cliente.id == models.Credito.cliente_id)
            .where(C.fecha_pago.isnot(None)))
    if desde:
        base = base.where(C.fecha_pago >= desde)
    if hasta:
        base = base.where(C.fecha_pago <= hasta)
    if credito_id:
        base = base.where(C.credito_id == credito_id)
    if via:
        base = base.where(C.via_pago == via)
    tot_q = base.with_only_columns(
        func.count(C.id), func.coalesce(func.sum(C.total_pagado), 0)).order_by(None)
    total, total_pagado = db.execute(tot_q).one()
    base = base.order_by(C.fecha_pago.desc(), C.id.desc()).limit(min(limit, cap)).offset(max(offset, 0))
    items = [{"credito_id": r.credito_id, "cuota": r.numero, "cliente": r.apellido_nombre,
              "fecha_pago": r.fecha_pago, "nro_recibo": r.nro_recibo,
              "via_pago": r.via_pago or "-", "cajero": r.usuario_pago or "-",
              "total_pagado": r.total_pagado}
             for r in db.execute(base).all()]
    return {"total": total, "limit": limit, "offset": offset,
            "total_pagado": Decimal(total_pagado), "items": items}


def resumen_cobros_creditos(db: Session, *, desde: date | None = None,
                            hasta: date | None = None) -> dict:
    """Resumen de cobros de créditos por período mensual (VFP: frm330150000rptcobcre).

    Agrega las cuotas efectivamente PAGADAS (la cobranza real que trae la migración vive en `cuotas`:
    fecha_pago + total_pagado + desglose por concepto). Por período: capital (amortización), interés,
    IVA-interés, seguro y gastos administrativos; la mora se infiere como residual (total pagado − la suma
    de conceptos), ya que la data migrada no la separa por cuota."""
    C = models.Cuota
    anio = func.extract("year", C.fecha_pago)     # portable PG/SQLite vía SQLAlchemy
    mes = func.extract("month", C.fecha_pago)
    S = lambda col: func.coalesce(func.sum(col), 0)  # noqa: E731
    q = (select(anio, mes, func.count(C.id), func.count(func.distinct(C.credito_id)),
                S(C.amortizacion), S(C.interes), S(C.iva_interes),
                S(C.seguro), S(C.gastos_adm), S(C.total_pagado))
         .where(C.fecha_pago.isnot(None))
         .group_by(anio, mes).order_by(anio.desc(), mes.desc()))
    if desde:
        q = q.where(C.fecha_pago >= desde)
    if hasta:
        q = q.where(C.fecha_pago <= hasta)

    D = Decimal
    claves = ("cuotas", "creditos", "capital", "interes", "iva", "mora", "seguro", "gastos", "total")
    items, tot = [], {k: D(0) for k in claves}
    for a, m, ncuo, ncre, cap, intr, iva, seg, gas, total in db.execute(q).all():
        cap, intr, iva, seg, gas, total = map(D, (cap, intr, iva, seg, gas, total))
        mora = max(D(0), total - (cap + intr + iva + seg + gas))   # residual = punitorios cobrados
        fila = {"periodo": f"{int(a)}-{int(m):02d}", "cuotas": int(ncuo), "creditos": int(ncre),
                "capital": cap, "interes": intr, "iva": iva, "mora": mora,
                "seguro": seg, "gastos": gas, "total": total}
        items.append(fila)
        for k in ("capital", "interes", "iva", "mora", "seguro", "gastos", "total"):
            tot[k] += fila[k]
        tot["cuotas"] += int(ncuo); tot["creditos"] += int(ncre)
    return {"items": items, "total": {k: (int(v) if k in ("cuotas", "creditos") else v)
                                      for k, v in tot.items()}}


def creditos_sin_debito(db: Session, *, q: str | None = None, linea_id: int | None = None,
                        limit: int = 25, offset: int = 0) -> dict:
    """Créditos activos cuyo cliente no tiene CBU: no se pueden debitar
    automáticamente, requieren cobro manual (VFP: frm315450500solsindeb;
    con `linea_id` cubre la variante "de Línea 25" frm315451000solsindeb25)."""
    base = (
        select(models.Credito, models.Cliente, models.LineaCredito)
        .join(models.Cliente, models.Cliente.id == models.Credito.cliente_id)
        .outerjoin(models.LineaCredito, models.LineaCredito.id == models.Credito.linea_id)
        .where(models.Credito.estado == "A")
        .where((models.Cliente.cbu == "") | (models.Cliente.cbu.is_(None)))
    )
    if linea_id:
        base = base.where(models.Credito.linea_id == linea_id)
    if q:
        like = f"%{q.upper()}%"
        base = base.where(models.Cliente.apellido_nombre.like(like)
                          | models.Cliente.cuil.like(like))
    tot_q = base.with_only_columns(
        func.count(models.Credito.id),
        func.coalesce(func.sum(models.Credito.saldo_capital), 0),
    ).order_by(None)
    total, total_saldo = db.execute(tot_q).one()
    base = base.order_by(models.Credito.id.desc()).limit(min(limit, 200)).offset(max(offset, 0))
    items = [{"credito_id": cr.id, "cliente": cli.apellido_nombre, "cuil": cli.cuil,
              "linea": lin.nombre if lin else "—", "saldo": cr.saldo_capital,
              "sueldo": cli.sueldo}
             for cr, cli, lin in db.execute(base).all()]
    return {"total": total, "limit": limit, "offset": offset,
            "total_saldo": Decimal(total_saldo), "items": items}


def cuenta_corriente(db: Session, credito_id: int) -> dict:
    """Movimientos de cuenta corriente de un crédito (VFP: ctacte)."""
    movs = db.scalars(select(models.MovimientoCta).where(
        models.MovimientoCta.credito_id == credito_id)
        .order_by(models.MovimientoCta.fecha, models.MovimientoCta.id)).all()
    items, saldo = [], CERO
    for m in movs:
        saldo += (m.debitos - m.creditos)
        items.append({"fecha": m.fecha, "cuota": m.cuota, "tipo": m.tipo,
                      "debitos": m.debitos, "creditos": m.creditos,
                      "capital": m.capital, "interes": m.interes, "iva": m.iva,
                      "punitorio": m.punitorio, "no_recibo": m.no_recibo,
                      "saldo": saldo})
    return {"credito_id": credito_id, "cantidad": len(items),
            "saldo_final": saldo, "movimientos": items}


def cuotas_en_mora(db: Session, fecha_corte: date) -> dict:
    """Cuotas vencidas impagas a la fecha (VFP: frm330600000ctasmora1)."""
    q = (
        select(models.Cuota, models.Credito, models.Cliente)
        .join(models.Credito, models.Credito.id == models.Cuota.credito_id)
        .join(models.Cliente, models.Cliente.id == models.Credito.cliente_id)
        .where(models.Cuota.estado != "P", models.Credito.estado == "A",
               models.Cuota.fecha_vencimiento < fecha_corte)
        .order_by(models.Cuota.fecha_vencimiento)
    )
    items = []
    total = CERO
    for cuota, credito, cliente in db.execute(q).all():
        dias = (fecha_corte - cuota.fecha_vencimiento).days
        pend = cuota.total - cuota.total_pagado
        items.append({"credito_id": credito.id, "cliente": cliente.apellido_nombre,
                      "cuota_numero": cuota.numero, "vencimiento": cuota.fecha_vencimiento,
                      "dias_mora": dias, "importe": pend})
        total += pend
    return {"fecha_corte": fecha_corte, "cantidad": len(items),
            "total": total, "items": items}


def envios(db: Session, desde: date, hasta: date) -> dict:
    """Cuotas a debitar por planilla en el período (débito automático)."""
    q = (
        select(models.Cuota, models.Credito, models.Cliente)
        .join(models.Credito, models.Credito.id == models.Cuota.credito_id)
        .join(models.Cliente, models.Cliente.id == models.Credito.cliente_id)
        .where(models.Cuota.estado != "P",
               models.Cuota.fecha_vencimiento >= desde,
               models.Cuota.fecha_vencimiento <= hasta,
               models.Credito.estado == "A")
        .order_by(models.Cuota.fecha_vencimiento)
    )
    items = []
    total = CERO
    for cuota, credito, cliente in db.execute(q).all():
        items.append({
            "credito_id": credito.id, "cliente": cliente.apellido_nombre,
            "cuil": cliente.cuil, "cbu": cliente.cbu,
            "cuota_numero": cuota.numero, "vencimiento": cuota.fecha_vencimiento,
            "importe": cuota.total,
        })
        total += cuota.total
    return {"desde": desde, "hasta": hasta, "cantidad": len(items),
            "total": total, "items": items}
