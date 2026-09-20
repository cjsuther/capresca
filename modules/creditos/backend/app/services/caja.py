"""Servicios del módulo Caja: cobranza de cuotas con mora e imputación.

La mora al cobrar usa `domain.mora.calcular_mora`, validado contra ivacob.DBF.
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


def cuotas_pendientes(db: Session, credito_id: int, fecha_pago: date) -> list[dict]:
    """Cuotas no pagadas de un crédito, con el importe adeudado (incluida mora)."""
    credito = db.get(models.Credito, credito_id)
    if not credito:
        raise ReglaNegocioError("Crédito inexistente")
    # Un crédito dado de baja/anulado (B) no tiene cuotas a cobrar.
    if credito.estado == "B":
        return []
    linea = _linea_de_credito(db, credito)
    cuotas = db.scalars(
        select(models.Cuota).where(
            models.Cuota.credito_id == credito_id,
            models.Cuota.estado.notin_(("P", "B")),   # ni pagadas ni anuladas
        ).order_by(models.Cuota.numero)
    ).all()
    out = []
    for c in cuotas:
        m = _mora_de_cuota(c, linea, fecha_pago)
        pendiente = (c.total - c.total_pagado)
        out.append({
            "cuota_id": c.id, "numero": c.numero,
            "fecha_vencimiento": c.fecha_vencimiento,
            "importe_cuota": c.total, "ya_pagado": c.total_pagado,
            "dias_mora": m.dias,
            "interes_punitorio": m.interes_punitorio,
            "iva_punitorio": m.iva_punitorio,
            "total_a_pagar": (pendiente + m.interes_punitorio + m.iva_punitorio),
        })
    return out


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


def anular_recibo(db: Session, recibo_id: int) -> models.Recibo:
    """Anula un recibo y revierte la cobranza (VFP: frm225250000anupago).

    Las cuotas vuelven a estado activo, se restaura el saldo del crédito y, si el
    crédito estaba cancelado, vuelve a activo.
    """
    recibo = db.get(models.Recibo, recibo_id)
    if not recibo:
        raise ReglaNegocioError("Recibo inexistente")
    if recibo.estado == "A":
        raise ReglaNegocioError("El recibo ya está anulado")

    # Un recibo puede abarcar varios créditos (cola de caja por persona): se
    # restaura el saldo de cada crédito según la cuota de cada pago.
    pagos = db.scalars(select(models.PagoCuota).where(
        models.PagoCuota.recibo_id == recibo.id)).all()
    creditos_tocados: set[int] = set()
    for p in pagos:
        cuota = db.get(models.Cuota, p.cuota_id)
        if cuota:
            cuota.estado = "A"
            cuota.total_pagado = CERO
            credito = db.get(models.Credito, cuota.credito_id)
            if credito:
                credito.saldo_capital = credito.saldo_capital + p.capital
                creditos_tocados.add(credito.id)
    for cid in creditos_tocados:
        credito = db.get(models.Credito, cid)
        if credito and credito.estado == "C":
            credito.estado = "A"
    recibo.estado = "A"
    db.commit()
    db.refresh(recibo)
    return recibo


def control_caja(db: Session, fecha: date, cajero: str | None = None) -> dict:
    """Control de caja de un día, detallado por cajero (VFP: frm225300000ctrlcaj)."""
    from collections import defaultdict
    qy = select(models.Recibo).where(models.Recibo.fecha_pago == fecha,
                                      models.Recibo.estado == "E")
    if cajero:
        qy = qy.where(models.Recibo.cajero == cajero)
    recibos = db.scalars(qy.order_by(models.Recibo.cajero, models.Recibo.numero)).all()

    por_cajero: dict[str, list] = defaultdict(list)
    for r in recibos:
        cliente = db.get(models.Cliente, r.cliente_id)
        por_cajero[r.cajero].append({
            "numero": r.numero, "cliente": cliente.apellido_nombre if cliente else "",
            "via_pago": r.via_pago, "total": r.total,
        })

    # Cobros de agencias de quiniela del día (cajapagos) — mismo control por cajero.
    qa = select(models.CajaPagoAgencia).where(
        models.CajaPagoAgencia.fecha_pago == fecha,
        models.CajaPagoAgencia.anulado.is_(False))
    if cajero:
        qa = qa.where(models.CajaPagoAgencia.cajero == cajero)
    pagos_ag = db.scalars(qa.order_by(models.CajaPagoAgencia.cajero,
                                      models.CajaPagoAgencia.no_recibo)).all()
    for p in pagos_ag:
        por_cajero[p.cajero].append({
            "numero": p.no_recibo, "cliente": f"Agencia {p.cod_agencia}",
            "via_pago": "QUINIELA", "total": p.cobrado_total,
        })

    cajeros = []
    total_general = CERO
    for caj, recs in por_cajero.items():
        subtotal = sum((x["total"] for x in recs), CERO)
        total_general += subtotal
        cajeros.append({"cajero": caj, "cantidad": len(recs),
                        "subtotal": subtotal, "recibos": recs})
    return {"fecha": fecha, "cajeros": cajeros,
            "cantidad_total": len(recibos) + len(pagos_ag),
            "total_general": total_general}


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


def _imputar_credito(db: Session, recibo: models.Recibo, credito: models.Credito,
                     numeros_cuota: list[int], fecha_pago: date) -> Decimal:
    """Imputa las cuotas de un crédito a un recibo (crea PagoCuota, actualiza saldo
    y cancela el crédito si no quedan pendientes). Devuelve el subtotal cobrado.
    Extraído para compartir entre el cobro por crédito y la cola de caja."""
    linea = _linea_de_credito(db, credito)
    cuotas = db.scalars(
        select(models.Cuota).where(
            models.Cuota.credito_id == credito.id,
            models.Cuota.numero.in_(numeros_cuota),
        )
    ).all()
    if len(cuotas) != len(set(numeros_cuota)):
        raise ReglaNegocioError(
            f"Alguna cuota indicada no existe en el crédito {credito.id}")
    pagables = [c for c in cuotas if c.estado != "P"]
    if not pagables:
        raise ReglaNegocioError(
            f"Las cuotas indicadas del crédito {credito.id} ya están pagadas")

    subtotal = CERO
    for c in sorted(pagables, key=lambda x: x.numero):
        m = _mora_de_cuota(c, linea, fecha_pago)
        pendiente = c.total - c.total_pagado
        total_cuota = pendiente + m.interes_punitorio + m.iva_punitorio
        db.add(models.PagoCuota(
            recibo_id=recibo.id, cuota_id=c.id,
            capital=c.amortizacion, interes=c.interes, iva_interes=c.iva_interes,
            seguro=c.seguro, gastos_adm=c.gastos_adm,
            interes_punitorio=m.interes_punitorio, iva_punitorio=m.iva_punitorio,
            dias_mora=m.dias, total_pagado=total_cuota,
        ))
        c.total_pagado = c.total
        c.estado = "P"
        credito.saldo_capital = credito.saldo_capital - c.amortizacion
        subtotal += total_cuota

    db.flush()  # persistir estados antes de contar pendientes
    restantes = db.scalar(
        select(func.count()).select_from(models.Cuota).where(
            models.Cuota.credito_id == credito.id, models.Cuota.estado != "P")
    )
    if restantes == 0:
        credito.estado = "C"
        credito.saldo_capital = CERO
    return subtotal


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


def recibos_del_dia(db: Session, *, fecha: date) -> dict:
    """Recibos emitidos en un día para reimpresión (VFP: frm230100000rptreci /
    rptrecihis, menú 23010/23012). Unifica los recibos de quiniela (`cajapagos`,
    origen JUEG) y los de créditos/seguros/extra (`cajacreseg`, agrupados por
    no_recibo). Columnas: N°Recibo, Cod.Age/Titular, Fecha, Origen, Importe, Cajero."""
    items = []
    # Quiniela: un recibo por cajapagos
    for p in db.scalars(select(models.CajaPagoAgencia).where(
            models.CajaPagoAgencia.fecha_pago == fecha,
            models.CajaPagoAgencia.anulado.is_(False))).all():
        items.append({
            "no_recibo": p.no_recibo, "cod_agencia": p.cod_agencia,
            "titular": f"Agencia {p.cod_agencia}", "origen": "JUEG",
            "fecha_pago": p.fecha_pago, "importe": p.cobrado_total, "cajero": p.cajero,
        })
    # Créditos/Seguros/Extra: agrupados por no_recibo
    C = models.CajaCreSeg
    q = (select(C.no_recibo, C.origen, C.cajero,
                func.max(C.apellido_nombre), func.coalesce(func.sum(C.total_gral), 0))
         .where(C.fecha_pago == fecha, C.pagado.is_(True), C.revertida.is_(False))
         .group_by(C.no_recibo, C.origen, C.cajero))
    for no_recibo, origen, cajero, nombre, importe in db.execute(q).all():
        items.append({
            "no_recibo": no_recibo, "cod_agencia": 0,
            "titular": nombre or "", "origen": origen,
            "fecha_pago": fecha, "importe": Decimal(importe), "cajero": cajero,
        })
    items.sort(key=lambda x: (x["origen"], x["no_recibo"]))
    total = sum((x["importe"] for x in items), CERO)
    return {"fecha": fecha, "cantidad": len(items), "total": total, "items": items}


def reimpresion_recibo(db: Session, *, no_recibo: int, origen: str, fecha: date) -> dict:
    """Datos de un recibo emitido para reimprimir (VFP: frm230100000rptreci). Arma la
    cabecera + líneas desde las tablas reales según el origen:
      - JUEG: `cajapagos` (cabecera) + `cajaliq` (líneas: juego/sorteo/moneda/total).
      - CRED/SEGU/EXTR: `cajacreseg` (líneas: cuota/capital/interés/IVA/punitorio)."""
    if origen == "JUEG":
        pago = db.scalar(select(models.CajaPagoAgencia).where(
            models.CajaPagoAgencia.no_recibo == no_recibo,
            models.CajaPagoAgencia.fecha_pago == fecha))
        if not pago:
            raise ReglaNegocioError("Recibo de quiniela inexistente")
        lineas = []
        for x in db.scalars(select(models.LiquidacionAgencia).where(
                models.LiquidacionAgencia.no_recibo == no_recibo,
                models.LiquidacionAgencia.cod_agencia == pago.cod_agencia)).all():
            lineas.append({"detalle": f"{x.juego} · sorteo {x.no_sorteo}",
                           "moneda": x.moneda, "importe": x.total_gral or x.total})
        cab = {"no_recibo": no_recibo, "origen": "Quiniela",
               "titular": f"Agencia {pago.cod_agencia}", "fecha": fecha,
               "cajero": pago.cajero, "total": pago.cobrado_total,
               "extra": (f"Bonos {pago.cobrado_bonos} · Pesos {pago.cobrado_pesos} · "
                         f"Vuelto {pago.vuelto_bonos + pago.vuelto_pesos}")}
        return {"cabecera": cab, "lineas": lineas}

    # Créditos / Seguros / Extraordinarios
    filas = db.scalars(select(models.CajaCreSeg).where(
        models.CajaCreSeg.no_recibo == no_recibo,
        models.CajaCreSeg.fecha_pago == fecha,
        models.CajaCreSeg.revertida.is_(False))).all()
    if not filas:
        raise ReglaNegocioError("Recibo inexistente")
    lineas, total = [], CERO
    for f in filas:
        total += f.total_gral
        lineas.append({
            "detalle": f"Créd. {f.no_credito or '-'} cuota {f.cuota or '-'}"
                       f" (cap {_money2(f.moncuo)} int {_money2(f.interes + f.interes_punit)}"
                       f" iva {_money2(f.iva_interes + f.iva_punit)})",
            "moneda": f.moneda, "importe": f.total_gral})
    nombre = filas[0].apellido_nombre
    cab = {"no_recibo": no_recibo,
           "origen": {"CRED": "Crédito", "SEGU": "Seguro"}.get(filas[0].origen, "Extraordinario"),
           "titular": nombre, "fecha": fecha, "cajero": filas[0].cajero,
           "total": total, "extra": ""}
    return {"cabecera": cab, "lineas": lineas}


def _money2(v) -> str:
    return f"{Decimal(v):,.2f}"


def pagos_realizados(db: Session, *, desde: date, hasta: date,
                     coding: int | None = None, texto: str | None = None,
                     limit: int = 500) -> dict:
    """Listado de pagos realizados (VFP: frm230250000lispag / menú 23025): registros
    de `cajacreseg` entre dos fechas (por fecha_pago), no revertidos, ordenados por
    coding/subing/fecha. Filtra por `coding` (tipo de ingreso: 50/80/81/82…) y por
    `texto` (búsqueda en el nombre)."""
    C = models.CajaCreSeg
    q = select(C).where(C.fecha_pago >= desde, C.fecha_pago <= hasta,
                        C.revertida.is_(False))
    if coding:
        q = q.where(C.coding == coding)
    if texto:
        q = q.where(C.apellido_nombre.ilike(f"%{texto.strip()}%"))
    q = q.order_by(C.coding, C.subing, C.fecha_pago)
    filas = db.scalars(q.limit(limit + 1)).all()
    truncado = len(filas) > limit
    filas = filas[:limit]
    # total sobre TODO el conjunto (no sólo la página)
    tot_q = select(func.count(C.id), func.coalesce(func.sum(C.total_gral), 0)).where(
        C.fecha_pago >= desde, C.fecha_pago <= hasta, C.revertida.is_(False))
    if coding:
        tot_q = tot_q.where(C.coding == coding)
    if texto:
        tot_q = tot_q.where(C.apellido_nombre.ilike(f"%{texto.strip()}%"))
    cantidad, total = db.execute(tot_q).one()
    items = [{
        "origen": f.origen, "coding": f.coding, "subing": f.subing,
        "no_credito": f.no_credito, "cuil": f.cuil, "dni": f.dni,
        "apellido_nombre": f.apellido_nombre, "cuota": f.cuota,
        "no_recibo": f.no_recibo, "cajero": f.cajero, "moneda": f.moneda,
        "fecha_pago": f.fecha_pago, "total": f.total_gral,
    } for f in filas]
    return {"desde": desde, "hasta": hasta, "cantidad": cantidad,
            "total": Decimal(total), "truncado": truncado, "items": items}


def planilla_contable_creditos(db: Session, *, fecha: date) -> dict:
    """Planilla para contabilidad: créditos cobrados en un día (VFP:
    frm230450000rciecre / menú 23045). Toma los cobros de `cajacreseg` origen=CRED
    del día (pagados, no revertidos) y los descompone por concepto contable
    (capital, interés, IVA, seguro, gastos, punitorio) para el asiento."""
    C = models.CajaCreSeg
    filas = db.scalars(select(C).where(
        C.origen == "CRED", C.pagado.is_(True), C.revertida.is_(False),
        C.fecha_pago == fecha)).all()
    acc = {
        "Capital": CERO, "Interés": CERO, "IVA s/interés": CERO,
        "Seguro": CERO, "IVA s/seguro": CERO, "Gastos adm.": CERO,
        "IVA s/gastos": CERO, "Interés punitorio": CERO, "IVA s/punitorio": CERO,
    }
    total = CERO
    for f in filas:
        acc["Capital"] += f.moncuo
        acc["Interés"] += f.interes
        acc["IVA s/interés"] += f.iva_interes
        acc["Seguro"] += f.seguro
        acc["IVA s/seguro"] += f.iva_seguro
        acc["Gastos adm."] += f.gastos
        acc["IVA s/gastos"] += f.iva_gastos
        acc["Interés punitorio"] += f.interes_punit
        acc["IVA s/punitorio"] += f.iva_punit
        total += f.total_gral
    conceptos = [{"concepto": k, "importe": v} for k, v in acc.items() if v]
    return {"fecha": fecha, "cantidad": len(filas), "conceptos": conceptos,
            "total": total}


def intereses_iva_mensual(db: Session, *, mes: int, anio: int) -> dict:
    """Reporte mensual de intereses e IVA (VFP: frm230150000rptinte / menú 23015):
    combina los intereses/IVA cobrados en el mes de dos fuentes —
    `cajacreseg` (créditos/seguros/extra: interés e IVA normal + punitorio) y
    `cajaliq` (quiniela: intereses + IVA)—, agrupados por origen."""
    import calendar
    from datetime import date as _date
    if not (1 <= mes <= 12):
        raise ReglaNegocioError("Mes inválido")
    desde = _date(anio, mes, 1)
    hasta = _date(anio, mes, calendar.monthrange(anio, mes)[1])

    items = []
    tot_int = tot_iva = CERO
    # Créditos / Seguros / Extra (cajacreseg), por origen
    C = models.CajaCreSeg
    q = (select(
            C.origen,
            func.count(C.id),
            func.coalesce(func.sum(C.interes), 0),
            func.coalesce(func.sum(C.iva_interes), 0),
            func.coalesce(func.sum(C.interes_punit), 0),
            func.coalesce(func.sum(C.iva_punit), 0),
         )
         .where(C.pagado.is_(True), C.revertida.is_(False),
                C.fecha_pago >= desde, C.fecha_pago <= hasta)
         .group_by(C.origen).order_by(C.origen))
    for origen, n, interes, ivain, ipun, ivapun in db.execute(q).all():
        interes, ivain, ipun, ivapun = (Decimal(x) for x in (interes, ivain, ipun, ivapun))
        it_int = interes + ipun
        it_iva = ivain + ivapun
        if it_int == 0 and it_iva == 0:
            continue
        tot_int += it_int; tot_iva += it_iva
        items.append({"origen": origen, "cantidad": n, "interes": interes,
                      "iva_interes": ivain, "interes_punit": ipun, "iva_punit": ivapun,
                      "total_interes": it_int, "total_iva": it_iva})
    # Quiniela (cajaliq): intereses + iva
    L = models.LiquidacionAgencia
    qj = (select(func.count(L.id), func.coalesce(func.sum(L.intereses), 0),
                 func.coalesce(func.sum(L.iva), 0))
          .where(L.pagado.is_(True), L.fecha_pago >= desde, L.fecha_pago <= hasta))
    nj, jint, jiva = db.execute(qj).one()
    jint, jiva = Decimal(jint), Decimal(jiva)
    if jint or jiva:
        tot_int += jint; tot_iva += jiva
        items.append({"origen": "JUEG", "cantidad": nj, "interes": jint,
                      "iva_interes": jiva, "interes_punit": CERO, "iva_punit": CERO,
                      "total_interes": jint, "total_iva": jiva})
    return {"mes": mes, "anio": anio, "items": items,
            "total_interes": tot_int, "total_iva": tot_iva,
            "total": tot_int + tot_iva}


def recaudacion_anual(db: Session, *, anio: int) -> dict:
    """Recaudación anual por origen y mes (VFP: frm230300000reca / menú 23030):
    agrupa por origen (CR créditos/seguros, JUEG quiniela) × mes del año, sumando lo
    recaudado y los premios. CR sale de `recibos`; JUEG de `cajapagos`."""
    from datetime import date as _date
    desde, hasta = _date(anio, 1, 1), _date(anio, 12, 31)

    def _fila_vacia(origen):
        return {"origen": origen, "meses": [CERO] * 12,
                "premios": [CERO] * 12, "total": CERO, "premios_total": CERO}

    cr = _fila_vacia("CR")
    recibos = db.scalars(select(models.Recibo).where(
        models.Recibo.fecha_pago >= desde, models.Recibo.fecha_pago <= hasta,
        models.Recibo.estado == "E")).all()
    for r in recibos:
        m = r.fecha_pago.month - 1
        cr["meses"][m] += r.total
        cr["total"] += r.total

    ju = _fila_vacia("JUEG")
    pagos = db.scalars(select(models.CajaPagoAgencia).where(
        models.CajaPagoAgencia.fecha_pago >= desde,
        models.CajaPagoAgencia.fecha_pago <= hasta,
        models.CajaPagoAgencia.anulado.is_(False))).all()
    for p in pagos:
        m = (p.fecha_pago.month - 1) if p.fecha_pago else 0
        pr = (p.premios_pesos or CERO) + (p.premios_bonos or CERO)
        ju["meses"][m] += p.cobrado_total
        ju["premios"][m] += pr
        ju["total"] += p.cobrado_total
        ju["premios_total"] += pr

    origenes = [f for f in (cr, ju) if f["total"] or f["premios_total"]]
    total_general = sum((f["total"] for f in origenes), CERO)
    return {"anio": anio, "origenes": origenes, "total_general": total_general}


def cobranzas_periodo(db: Session, *, desde: date, hasta: date,
                      origen: str | None = None) -> dict:
    """Informe de cobranzas en un período (VFP: frminformecobros / menú 23065):
    unifica los recibos de **créditos/seguros** (`recibos`) y los cobros de
    **quiniela** (`cajapagos`) entre dos fechas, con su total. `origen` filtra
    'CR' (créditos/seguros) o 'JUEG' (quiniela)."""
    items = []
    total_cr = total_ju = CERO
    if origen in (None, "CR"):
        recibos = db.scalars(select(models.Recibo).where(
            models.Recibo.fecha_pago >= desde, models.Recibo.fecha_pago <= hasta,
            models.Recibo.estado == "E").order_by(models.Recibo.fecha_pago,
                                                   models.Recibo.numero)).all()
        for r in recibos:
            cli = db.get(models.Cliente, r.cliente_id)
            total_cr += r.total
            items.append({
                "origen": "CR", "denominacion": "Crédito/Seguro",
                "nombres": cli.apellido_nombre if cli else "", "dni": cli.dni if cli else "",
                "no_recibo": r.numero, "fecha_pago": r.fecha_pago,
                "via_pago": r.via_pago, "cajero": r.cajero, "total": r.total,
            })
    if origen in (None, "JUEG"):
        pagos = db.scalars(select(models.CajaPagoAgencia).where(
            models.CajaPagoAgencia.fecha_pago >= desde,
            models.CajaPagoAgencia.fecha_pago <= hasta,
            models.CajaPagoAgencia.anulado.is_(False)).order_by(
                models.CajaPagoAgencia.fecha_pago,
                models.CajaPagoAgencia.no_recibo)).all()
        for p in pagos:
            total_ju += p.cobrado_total
            items.append({
                "origen": "JUEG", "denominacion": f"Agencia {p.cod_agencia}",
                "nombres": "", "dni": "", "no_recibo": p.no_recibo,
                "fecha_pago": p.fecha_pago, "via_pago": "QUINIELA",
                "cajero": p.cajero, "total": p.cobrado_total,
            })
    items.sort(key=lambda x: (x["fecha_pago"] or date.min, x["no_recibo"]))
    return {"desde": desde, "hasta": hasta, "cantidad": len(items),
            "total_creditos": total_cr, "total_quiniela": total_ju,
            "total": total_cr + total_ju, "items": items}


def cobrar(db: Session, credito_id: int, numeros_cuota: list[int],
           fecha_pago: date, via_pago: str, cajero: str) -> models.Recibo:
    """Cobra las cuotas indicadas de UN crédito (pago completo por cuota)."""
    credito = db.get(models.Credito, credito_id)
    if not credito:
        raise ReglaNegocioError("Crédito inexistente")
    if credito.estado == "C":
        raise ReglaNegocioError("El crédito ya está cancelado")

    recibo = _emitir_recibo(
        db, fecha_pago=fecha_pago, cliente_id=credito.cliente_id,
        credito_id=credito.id, cajero=cajero, via_pago=via_pago, estado="E")
    recibo.total = _imputar_credito(db, recibo, credito, numeros_cuota, fecha_pago)

    from app.services import contabilidad
    contabilidad.asiento_cobranza(db, recibo)
    db.commit()
    db.refresh(recibo)
    return recibo


# ---------------- Cola de caja por persona (VFP: frm225150000cresegu1) ----------------
def cola_de_caja(db: Session, *, fecha: date, cuil: str | None = None,
                 dni: str | None = None, nombre: str | None = None) -> dict:
    """Cola de caja de una persona: todas las cuotas pendientes de TODOS sus
    créditos, en la forma del cursor `cajacreseg` (Origen, F.Alta, DNI, Nombre,
    N°Crédito, N°Cta, Importe, Interés, IVA, Total). Reproduce la cobranza de
    Créditos/Seguros/Extraordinarios que agrupa por persona, no por crédito."""
    cli_q = select(models.Cliente)
    if cuil:
        cli_q = cli_q.where(models.Cliente.cuil == cuil.strip())
    elif dni:
        cli_q = cli_q.where(models.Cliente.dni == dni.strip())
    elif nombre:
        cli_q = cli_q.where(models.Cliente.apellido_nombre.ilike(f"%{nombre.strip()}%"))
    else:
        raise ReglaNegocioError("Indicá CUIL, DNI o nombre para buscar la cola")
    clientes = db.scalars(cli_q.order_by(models.Cliente.apellido_nombre).limit(50)).all()
    if not clientes:
        return {"clientes": [], "items": [], "total": CERO, "cantidad": 0}

    items, total = [], CERO
    resumen_cli = []
    for cli in clientes:
        creditos = db.scalars(select(models.Credito).where(
            models.Credito.cliente_id == cli.id,
            models.Credito.estado == "A")).all()
        sub_cli = CERO
        for cr in creditos:
            linea = _linea_de_credito(db, cr)
            cuotas = db.scalars(select(models.Cuota).where(
                models.Cuota.credito_id == cr.id,
                models.Cuota.estado != "P").order_by(models.Cuota.numero)).all()
            for c in cuotas:
                m = _mora_de_cuota(c, linea, fecha)
                pendiente = c.total - c.total_pagado
                tot = pendiente + m.interes_punitorio + m.iva_punitorio
                items.append({
                    "origen": "CR", "f_alta": cr.fecha_otorgamiento,
                    "dni": cli.dni, "cuil": cli.cuil,
                    "apellido_nombre": cli.apellido_nombre,
                    "cliente_id": cli.id, "credito_id": cr.id, "cuota": c.numero,
                    "importe": pendiente,
                    "interes": m.interes_punitorio, "iva": m.iva_punitorio,
                    "dias_mora": m.dias, "total": tot,
                })
                total += tot
                sub_cli += tot
        resumen_cli.append({"cliente_id": cli.id, "cuil": cli.cuil, "dni": cli.dni,
                            "apellido_nombre": cli.apellido_nombre, "total": sub_cli})
    return {"clientes": resumen_cli, "items": items,
            "total": total, "cantidad": len(items)}


def cobrar_cola(db: Session, *, items: list[dict], fecha_pago: date,
                via_pago: str, cajero: str) -> models.Recibo:
    """Cobra una selección de la cola (posiblemente de varios créditos de la misma
    persona) bajo UN recibo. `items` = [{credito_id, cuotas:[nums]}]."""
    if not items:
        raise ReglaNegocioError("Seleccioná al menos una cuota de la cola")
    # agrupar cuotas por crédito
    por_credito: dict[int, list[int]] = {}
    for it in items:
        por_credito.setdefault(int(it["credito_id"]), []).extend(
            int(n) for n in it["cuotas"])
    creditos = {cid: db.get(models.Credito, cid) for cid in por_credito}
    for cid, cr in creditos.items():
        if not cr:
            raise ReglaNegocioError(f"Crédito {cid} inexistente")
        if cr.estado == "C":
            raise ReglaNegocioError(f"El crédito {cid} ya está cancelado")
    # el recibo se emite a nombre del cliente del primer crédito (misma persona)
    primero = creditos[next(iter(creditos))]
    recibo = _emitir_recibo(
        db, fecha_pago=fecha_pago, cliente_id=primero.cliente_id, credito_id=primero.id,
        cajero=cajero, via_pago=via_pago, estado="E")
    total = CERO
    for cid, nums in por_credito.items():
        total += _imputar_credito(db, recibo, creditos[cid], nums, fecha_pago)
    recibo.total = total

    from app.services import contabilidad
    contabilidad.asiento_cobranza(db, recibo)
    db.commit()
    db.refresh(recibo)
    return recibo
