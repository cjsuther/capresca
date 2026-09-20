"""Servicios del módulo Juegos/Quiniela: agencias y liquidaciones."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app import models

CERO = Decimal("0.00")


class ReglaNegocioError(Exception):
    pass


def resumen(db: Session, desde: date | None = None, hasta: date | None = None) -> dict:
    """Totales de recaudación, premios, comisiones y multas del período."""
    q = select(
        func.count(models.LiquidacionAgencia.id),
        func.coalesce(func.sum(models.LiquidacionAgencia.recaudacion), 0),
        func.coalesce(func.sum(models.LiquidacionAgencia.premios), 0),
        func.coalesce(func.sum(models.LiquidacionAgencia.comision_agencia), 0),
        func.coalesce(func.sum(models.LiquidacionAgencia.multas), 0),
        func.coalesce(func.sum(models.LiquidacionAgencia.total), 0),
    )
    if desde:
        q = q.where(models.LiquidacionAgencia.fecha_sorteo >= desde)
    if hasta:
        q = q.where(models.LiquidacionAgencia.fecha_sorteo <= hasta)
    n, rec, pre, com, mul, tot = db.execute(q).one()
    return {"cantidad": n, "recaudacion": Decimal(rec), "premios": Decimal(pre),
            "comisiones": Decimal(com), "multas": Decimal(mul), "total": Decimal(tot)}


def ingresos_por_juego(db: Session, desde: date | None = None,
                       hasta: date | None = None) -> list[dict]:
    """Recaudación/premios/comisiones agrupados por juego (VFP: resrec,
    inf_ingresos_jueg, rptingbru). El neto es recaudación - premios - comisiones."""
    L = models.LiquidacionAgencia
    q = select(
        L.juego,
        func.count(L.id),
        func.coalesce(func.sum(L.recaudacion), 0),
        func.coalesce(func.sum(L.premios), 0),
        func.coalesce(func.sum(L.comision_agencia + L.comision_subagencia), 0),
        func.coalesce(func.sum(L.total), 0),
    ).group_by(L.juego).order_by(func.sum(L.recaudacion).desc())
    if desde:
        q = q.where(L.fecha_sorteo >= desde)
    if hasta:
        q = q.where(L.fecha_sorteo <= hasta)
    filas = []
    for juego, n, rec, pre, com, tot in db.execute(q).all():
        rec, pre, com, tot = (Decimal(x) for x in (rec, pre, com, tot))
        # En el backup los premios se guardan como débito (negativo). Normalizamos
        # a la magnitud pagada a ganadores (ver hallazgo H-019).
        premios = abs(pre)
        filas.append({
            "juego": juego or "(sin juego)", "cantidad": n,
            "recaudacion": rec, "premios": premios, "comisiones": com,
            "neto": rec - premios - com, "total": tot,
        })
    return filas


def deuda_agencia_informe(db: Session, *, cod_agencia: int | None = None,
                          desde: date | None = None, hasta: date | None = None) -> dict:
    """Informe de deuda de agencia (VFP: frm225550000infdeuage / menú 22555): las
    liquidaciones **impagas** de una agencia (o todas) por rango de `fecha_vto`, con
    los días de atraso de las vencidas. Reproduce la consulta del form (para las
    vencidas con total>0 el sistema recalcula interés; se informa el atraso y el
    total_gral cargado)."""
    from datetime import date as _date
    L = models.LiquidacionAgencia
    q = select(L).where(L.pagado.is_(False))
    if cod_agencia:
        q = q.where(L.cod_agencia == cod_agencia)
    if desde:
        q = q.where(L.fecha_vto >= desde)
    if hasta:
        q = q.where(L.fecha_vto <= hasta)
    liqs = db.scalars(q.order_by(L.fecha_vto, L.cod_juego, L.fecha_sorteo)).all()
    hoy = _date.today()
    items, total = [], CERO
    for x in liqs:
        importe = x.total_gral or x.total
        dias = (hoy - x.fecha_vto).days if (x.fecha_vto and x.fecha_vto < hoy) else 0
        total += importe
        items.append({
            "cod_agencia": x.cod_agencia, "no_agencia": x.no_agencia,
            "subagencia": x.subagencia, "cod_juego": x.cod_juego, "juego": x.juego,
            "no_sorteo": x.no_sorteo, "fecha_sorteo": x.fecha_sorteo,
            "moneda": x.moneda, "total": x.total, "intereses": x.intereses,
            "iva": x.iva, "total_gral": importe, "fecha_vto": x.fecha_vto,
            "dias_atraso": dias,
        })
    return {"cod_agencia": cod_agencia, "cantidad": len(items),
            "total": total, "items": items}


def fondo_garantia(db: Session, *, cod_agencia: int | None = None,
                   no_agencia: int | None = None, subagencia: int | None = None,
                   desde: date | None = None, hasta: date | None = None) -> dict:
    """Informe de Fondo de Garantía (VFP: frm430250000infor_f_gara / menú 43025).

    Reproduce el `SELECT * FROM jghisliq UNION ALL SELECT * FROM liquidaciones` del
    form: suma el `fdo_gtia` de las liquidaciones **históricas + vigentes**, agrupado
    por agencia/subagencia, con detalle por juego. Filtra por agencia (todas o una)
    y por rango de `fecha` (todos los períodos si no se indica). En la tabla vigente
    la fecha del sorteo es `fecha_sorteo`; en la histórica es `fecha`."""
    H = models.LiquidacionHistorica
    L = models.LiquidacionAgencia

    def _agg(modelo, fecha_col, agc_col):
        q = select(agc_col, modelo.no_agencia, modelo.subagencia,
                   modelo.cod_juego,
                   func.count(), func.coalesce(func.sum(modelo.fdo_gtia), 0))
        if no_agencia is not None:
            q = q.where(modelo.no_agencia == no_agencia)
            if subagencia is not None:
                q = q.where(modelo.subagencia == subagencia)
        if cod_agencia is not None:
            q = q.where(agc_col == cod_agencia)
        if desde:
            q = q.where(fecha_col >= desde)
        if hasta:
            q = q.where(fecha_col <= hasta)
        q = q.group_by(agc_col, modelo.no_agencia, modelo.subagencia, modelo.cod_juego)
        return db.execute(q).all()

    # Une histórico + vigentes acumulando por (agencia, subagencia, juego).
    acc: dict[tuple, dict] = {}
    for rows in (_agg(H, H.fecha, H.cod_agencia), _agg(L, L.fecha_sorteo, L.cod_agencia)):
        for cod_ag, no_ag, sub, cod_juego, n, fdo in rows:
            key = (no_ag, sub, cod_juego)
            d = acc.setdefault(key, {"cod_agencia": cod_ag, "no_agencia": no_ag,
                                     "subagencia": sub, "cod_juego": cod_juego,
                                     "liquidaciones": 0, "fdo_gtia": CERO})
            d["liquidaciones"] += int(n)
            d["fdo_gtia"] += Decimal(fdo)

    # Nombres de juego para presentación (por código; la denominación se repite
    # entre modalidades, alcanza con una).
    juegos = {}
    for jg in db.scalars(select(models.Juego)).all():
        juegos.setdefault(jg.codigo, jg.denominacion)

    detalle = sorted(acc.values(), key=lambda d: (d["no_agencia"], d["subagencia"], d["cod_juego"]))
    for d in detalle:
        d["juego"] = juegos.get(d["cod_juego"], f"Juego {d['cod_juego']}")
        d["titular"] = ""

    # Subtotales por agencia y total general.
    por_agencia: dict[tuple, dict] = {}
    for d in detalle:
        k = (d["no_agencia"], d["subagencia"])
        a = por_agencia.setdefault(k, {"no_agencia": d["no_agencia"], "subagencia": d["subagencia"],
                                       "liquidaciones": 0, "fdo_gtia": CERO})
        a["liquidaciones"] += d["liquidaciones"]
        a["fdo_gtia"] += d["fdo_gtia"]
    agencias_out = sorted(por_agencia.values(), key=lambda a: (a["no_agencia"], a["subagencia"]))
    total = sum((a["fdo_gtia"] for a in agencias_out), CERO)

    return {"desde": desde, "hasta": hasta, "cantidad_agencias": len(agencias_out),
            "total_fdo_gtia": total, "agencias": agencias_out, "detalle": detalle}


def ingresos_brutos_periodo(db: Session, *, mes: int, anio: int) -> dict:
    """Informe de Ingresos Brutos por período (VFP: frm230350000infingbru / menú
    23035): agrupa las liquidaciones **cobradas** en el mes/año por agencia, sumando
    recaudación, comisiones (agencia+subagencia) e ing_brutos (retención). El período
    es el de la retención = mes de `fecha_pago` (todas las filas con ing_brutos tienen
    fecha_pago cargada)."""
    import calendar
    from datetime import date as _date
    if not (1 <= mes <= 12):
        raise ReglaNegocioError("Mes inválido")
    desde = _date(anio, mes, 1)
    hasta = _date(anio, mes, calendar.monthrange(anio, mes)[1])
    L = models.LiquidacionAgencia
    q = (select(
            L.cod_agencia, L.no_agencia, L.subagencia,
            func.count(L.id),
            func.coalesce(func.sum(L.recaudacion), 0),
            func.coalesce(func.sum(L.comision_agencia + L.comision_subagencia), 0),
            func.coalesce(func.sum(L.ing_brutos), 0),
         )
         .where(L.pagado.is_(True), L.fecha_pago >= desde, L.fecha_pago <= hasta)
         .group_by(L.cod_agencia, L.no_agencia, L.subagencia)
         .order_by(func.sum(L.ing_brutos).desc()))
    filas = []
    tot_rec = tot_com = tot_ib = CERO
    for cod, noag, sub, n, rec, com, ib in db.execute(q).all():
        rec, com, ib = Decimal(rec), Decimal(com), Decimal(ib)
        tot_rec += rec; tot_com += com; tot_ib += ib
        filas.append({"cod_agencia": cod, "no_agencia": noag, "subagencia": sub,
                      "cantidad": n, "recaudacion": rec, "comisiones": com,
                      "ing_brutos": ib})
    return {"mes": mes, "anio": anio, "cantidad_agencias": len(filas),
            "total_recaudacion": tot_rec, "total_comisiones": tot_com,
            "total_ing_brutos": tot_ib, "items": filas}


def premios_compensados(db: Session, *, fecha_vto: date) -> dict:
    """Informe de premios compensados por capital/interior (VFP:
    frm230550000premioscompensados / menú 23055): agrupa `cajaliq` por interior
    (Capital/Interior) y agencia para una `fecha_vto`, sumando total, premios,
    comisión de premios y total_gral. Muestra cómo los premios compensan la deuda."""
    from collections import defaultdict
    L = models.LiquidacionAgencia
    q = (select(
            L.interior, L.cod_agencia, L.no_agencia, L.subagencia,
            func.coalesce(func.sum(L.total), 0),
            func.coalesce(func.sum(L.premios), 0),
            func.coalesce(func.sum(L.com_premios), 0),
            func.coalesce(func.sum(L.total_gral), 0),
         )
         .where(L.fecha_vto == fecha_vto)
         .group_by(L.interior, L.cod_agencia, L.no_agencia, L.subagencia)
         .order_by(L.interior, L.cod_agencia))
    grupos = {"Capital": [], "Interior": []}
    tot = {"Capital": CERO, "Interior": CERO}
    for interior, cod, noag, sub, total, prem, comp, tg in db.execute(q).all():
        clave = "Interior" if interior else "Capital"
        tg = Decimal(tg)
        tot[clave] += tg
        grupos[clave].append({
            "cod_agencia": cod, "no_agencia": noag, "subagencia": sub,
            "total": Decimal(total), "premios": abs(Decimal(prem)),
            "com_premios": Decimal(comp), "total_gral": tg,
        })
    salida = [{"grupo": k, "cantidad": len(grupos[k]), "total_gral": tot[k],
               "items": grupos[k]} for k in ("Capital", "Interior") if grupos[k]]
    return {"fecha_vto": fecha_vto, "grupos": salida,
            "total_general": tot["Capital"] + tot["Interior"]}


def cheques_agencias(db: Session, *, fecha_vto: date, umbral: Decimal = Decimal("-10000")) -> dict:
    """Listado de cheques para agencias (VFP: frm230570000listado_cheques / menú
    23057): agrupa `cajaliq` por agencia para una `fecha_vto` y lista las que tienen
    `SUM(total_gral) <= -10000` — la caja les debe (premios superan la deuda), así que
    se les emite un cheque por el neto. El importe del cheque es la magnitud del neto."""
    L = models.LiquidacionAgencia
    q = (select(
            L.cod_agencia,
            func.coalesce(func.sum(L.premios), 0),
            func.coalesce(func.sum(L.total), 0),
            func.coalesce(func.sum(L.intereses), 0),
            func.coalesce(func.sum(L.iva), 0),
            func.coalesce(func.sum(L.total_gral), 0),
         )
         .where(L.fecha_vto == fecha_vto)
         .group_by(L.cod_agencia)
         .having(func.coalesce(func.sum(L.total_gral), 0) <= umbral)
         .order_by(L.cod_agencia))
    items, total = [], CERO
    for cod, prem, tot, inte, iva, tg in db.execute(q).all():
        tg = Decimal(tg)
        cheque = -tg   # neto negativo → importe del cheque a favor de la agencia
        total += cheque
        items.append({
            "cod_agencia": cod, "premios": abs(Decimal(prem)), "total": Decimal(tot),
            "intereses": Decimal(inte), "iva": Decimal(iva),
            "neto": tg, "cheque": cheque,
        })
    return {"fecha_vto": fecha_vto, "cantidad": len(items),
            "total_cheques": total, "items": items}


def premios_quiniela(db: Session, *, fecha: date, modo: str = "cobradas") -> dict:
    """Control de premios de quiniela (egresos) de un día (VFP: frm230200000prequi /
    menú 23020). `cajaliq` con premios != 0. Modos (optiongroup del form):
      - 'cobradas' (1): pagadas con fecha_pago = día → orden cajero/recibo/juego.
      - 'pendientes' (2): impagas con fecha_vto = día → orden moneda/juego/agencia.
      - 'ambas' (3): fecha_vto = día O fecha_pago = día.
    Los premios se guardan en negativo (débito); se informa la magnitud (H-019)."""
    from collections import defaultdict
    L = models.LiquidacionAgencia
    q = select(L).where(L.premios != 0)
    if modo == "pendientes":
        q = q.where(L.pagado.is_(False), L.fecha_vto == fecha)
        q = q.order_by(L.moneda, L.cod_juego, L.no_agencia, L.subagencia)
    elif modo == "ambas":
        q = q.where((L.fecha_vto == fecha) | (L.fecha_pago == fecha))
        q = q.order_by(L.cajero, L.no_recibo, L.cod_juego)
    else:  # cobradas (1)
        modo = "cobradas"
        q = q.where(L.pagado.is_(True), L.fecha_pago == fecha)
        q = q.order_by(L.cajero, L.no_recibo, L.cod_juego)
    liqs = db.scalars(q).all()

    items, total = [], CERO
    por_cajero: dict[str, list] = defaultdict(lambda: [0, CERO])
    for x in liqs:
        premio = abs(x.premios)
        total += premio
        por_cajero[x.cajero][0] += 1
        por_cajero[x.cajero][1] += premio
        items.append({
            "cajero": x.cajero, "no_recibo": x.no_recibo, "cod_agencia": x.cod_agencia,
            "no_agencia": x.no_agencia, "subagencia": x.subagencia,
            "cod_juego": x.cod_juego, "juego": x.juego, "no_sorteo": x.no_sorteo,
            "moneda": x.moneda, "premio": premio,
        })
    resumen = [{"cajero": c, "cantidad": v[0], "total": v[1]}
               for c, v in sorted(por_cajero.items())]
    return {"fecha": fecha, "modo": modo, "cantidad": len(items),
            "total": total, "resumen": resumen, "items": items}


def liquidaciones_cobradas(db: Session, *, fecha: date) -> dict:
    """Liquidaciones cobradas/pagadas en un día (VFP: frm230500000liqcob / menú
    23050): cajaliq con pagado y fecha_pago = fecha, ordenadas por cajero, recibo y
    juego. Devuelve el detalle, un resumen por cajero y el total."""
    from collections import defaultdict
    L = models.LiquidacionAgencia
    liqs = db.scalars(select(L).where(
        L.pagado.is_(True), L.fecha_pago == fecha
    ).order_by(L.cajero, L.no_recibo, L.cod_juego)).all()
    items, total = [], CERO
    por_cajero: dict[str, list] = defaultdict(lambda: [0, CERO])  # [cantidad, total]
    for x in liqs:
        importe = x.total_gral or x.total
        total += importe
        por_cajero[x.cajero][0] += 1
        por_cajero[x.cajero][1] += importe
        items.append({
            "cajero": x.cajero, "no_recibo": x.no_recibo, "cod_agencia": x.cod_agencia,
            "cod_juego": x.cod_juego, "juego": x.juego, "no_sorteo": x.no_sorteo,
            "moneda": x.moneda, "total_gral": importe,
        })
    resumen = [{"cajero": c, "cantidad": v[0], "total": v[1]}
               for c, v in sorted(por_cajero.items())]
    return {"fecha": fecha, "cantidad": len(items), "total": total,
            "resumen": resumen, "items": items}


def _proximo_recibo_agencia(db: Session) -> int:
    return (db.scalar(select(func.max(models.CajaPagoAgencia.no_recibo))) or 0) + 1


def deuda_agencia(db: Session, cod_agencia: int) -> dict:
    """Liquidaciones pendientes de una agencia, separadas por moneda (bonos/pesos).
    Reproduce el arranque del Aplicativo de Caja (frm225050000aplicaj)."""
    L = models.LiquidacionAgencia
    liqs = db.scalars(select(L).where(
        L.cod_agencia == cod_agencia, L.pagado.is_(False)
    ).order_by(L.fecha_sorteo, L.cod_juego)).all()
    bonos = pesos = CERO
    items = []
    for x in liqs:
        importe = x.total_gral or x.total
        es_bono = (x.moneda or "$").strip().upper() in ("B", "B$")
        if es_bono:
            bonos += importe
        else:
            pesos += importe
        items.append({
            "id": x.id, "cod_juego": x.cod_juego, "juego": x.juego,
            "no_sorteo": x.no_sorteo, "fecha_sorteo": x.fecha_sorteo,
            "no_agencia": x.no_agencia, "subagencia": x.subagencia,
            "moneda": x.moneda, "total": x.total, "intereses": x.intereses,
            "iva": x.iva, "total_gral": importe, "fecha_vto": x.fecha_vto,
        })
    return {"cod_agencia": cod_agencia, "cantidad": len(items),
            "bonos": bonos, "pesos": pesos, "total": bonos + pesos, "items": items}


def cobrar_agencia(db: Session, *, cod_agencia: int, formas_pago: list[dict],
                   premios_bonos: Decimal = CERO, premios_pesos: Decimal = CERO,
                   cajero: str, fecha: date | None = None) -> models.CajaPagoAgencia:
    """Cobra TODA la deuda pendiente de una agencia de quiniela (frm225050000aplicaj,
    Command1/Command2). `formas_pago` = [{moneda:'B'|'$', importe, cheque?}].

    En el sistema real la cobranza de agencia **salda el total** (verificado: de 31.530
    recibos reales, 31.529 tienen cobrado_total = total y 0 son parciales). Por eso el
    importe entregado en cada moneda **debe cubrir** la deuda de esa moneda; si no,
    se rechaza (no hay cobro parcial). Lo aplicado a la deuda es el total adeudado y el
    excedente entregado es el **vuelto** (cambio a devolver)."""
    from decimal import Decimal as _D
    deuda = deuda_agencia(db, cod_agencia)
    if not deuda["items"]:
        raise ReglaNegocioError("La agencia no tiene liquidaciones pendientes")
    bonos_ad, pesos_ad = deuda["bonos"], deuda["pesos"]

    entregado_bonos = entregado_pesos = CERO
    for fp in formas_pago:
        imp = _D(str(fp.get("importe", 0)))
        if str(fp.get("moneda", "$")).strip().upper() in ("B", "B$"):
            entregado_bonos += imp
        else:
            entregado_pesos += imp
    if entregado_bonos < bonos_ad or entregado_pesos < pesos_ad:
        raise ReglaNegocioError(
            f"El cobro no cubre la deuda de la agencia (adeudado bonos {bonos_ad} / "
            f"pesos {pesos_ad}; entregado bonos {entregado_bonos} / pesos {entregado_pesos}). "
            f"La cobranza de agencia salda el total, no admite pago parcial.")
    # cobrado = lo aplicado a la deuda (= total adeudado); vuelto = excedente entregado
    vuelto_bonos = entregado_bonos - bonos_ad
    vuelto_pesos = entregado_pesos - pesos_ad

    from app.core.numbering import crear_con_numero_unico

    def _construir(n):
        p = models.CajaPagoAgencia(
            cod_agencia=cod_agencia, fecha_pago=fecha or date.today(), origen="JUEG",
            no_recibo=n, bonos=bonos_ad, pesos=pesos_ad, total=deuda["total"],
            cobrado_bonos=bonos_ad, cobrado_pesos=pesos_ad,
            cobrado_total=deuda["total"], vuelto_bonos=vuelto_bonos,
            vuelto_pesos=vuelto_pesos, premios_bonos=_D(str(premios_bonos)),
            premios_pesos=_D(str(premios_pesos)), cajero=cajero, anulado=False,
        )
        db.add(p)
        return p
    pago = crear_con_numero_unico(db, lambda: _proximo_recibo_agencia(db), _construir)   # árbitro DB (H-108)
    # marcar liquidaciones cobradas
    for it in deuda["items"]:
        liq = db.get(models.LiquidacionAgencia, it["id"])
        liq.pagado = True
        liq.no_recibo = pago.no_recibo
        liq.fecha_pago = fecha or date.today()
        liq.cajero = cajero
    db.commit()
    db.refresh(pago)
    return pago


def anular_pago_agencia(db: Session, pago_id: int) -> models.CajaPagoAgencia:
    """Anula un recibo de cobro de agencia y revierte las liquidaciones."""
    pago = db.get(models.CajaPagoAgencia, pago_id)
    if not pago:
        raise ReglaNegocioError("Recibo de agencia inexistente")
    if pago.anulado:
        raise ReglaNegocioError("El recibo ya está anulado")
    liqs = db.scalars(select(models.LiquidacionAgencia).where(
        models.LiquidacionAgencia.no_recibo == pago.no_recibo,
        models.LiquidacionAgencia.cod_agencia == pago.cod_agencia)).all()
    for liq in liqs:
        liq.pagado = False
        liq.no_recibo = 0
        liq.fecha_pago = None
        liq.cajero = ""
    pago.anulado = True
    db.commit()
    db.refresh(pago)
    return pago


def cobrar_liquidacion(db: Session, liq_id: int, cajero: str,
                       no_recibo: int) -> models.LiquidacionAgencia:
    liq = db.get(models.LiquidacionAgencia, liq_id)
    if not liq:
        raise ReglaNegocioError("Liquidación inexistente")
    if liq.pagado:
        raise ReglaNegocioError("La liquidación ya está cobrada")
    liq.pagado = True
    liq.no_recibo = no_recibo
    db.commit()
    db.refresh(liq)
    return liq


def agencia_historico(db: Session, *, no_agencia: int, desde: date | None = None,
                      hasta: date | None = None, limit: int = 100) -> dict:
    """Histórico de una agencia (VFP: Caja/cj_liqhis.dbf + cj_paghis.dbf):
    liquidaciones y pagos archivados, con totales."""
    LH = models.LiquidacionAgenciaHistorica
    PH = models.CajaPagoAgenciaHistorico
    ql = select(LH).where(LH.no_agencia == no_agencia)
    if desde:
        ql = ql.where(LH.fecha_sorteo >= desde)
    if hasta:
        ql = ql.where(LH.fecha_sorteo <= hasta)
    liqs = db.scalars(ql.order_by(LH.fecha_sorteo.desc()).limit(limit)).all()
    tot_liq = db.scalar(select(func.count()).select_from(ql.subquery())) or 0
    imp_liq = Decimal(db.scalar(
        select(func.coalesce(func.sum(ql.subquery().c.total_gral), 0))) or 0)

    qp = select(PH).where(PH.cod_agencia == no_agencia)
    if desde:
        qp = qp.where(PH.fecha_pago >= desde)
    if hasta:
        qp = qp.where(PH.fecha_pago <= hasta)
    pagos = db.scalars(qp.order_by(PH.fecha_pago.desc()).limit(limit)).all()
    tot_pag = db.scalar(select(func.count()).select_from(qp.subquery())) or 0
    imp_pag = Decimal(db.scalar(
        select(func.coalesce(func.sum(qp.subquery().c.cobrado_total), 0))) or 0)

    return {
        "no_agencia": no_agencia,
        "liquidaciones": {
            "total": tot_liq, "importe": imp_liq,
            "items": [{"cod_juego": l.cod_juego, "juego": l.juego, "no_sorteo": l.no_sorteo,
                       "fecha_sorteo": l.fecha_sorteo, "recaudacion": l.recaudacion,
                       "total_gral": l.total_gral, "fecha_vto": l.fecha_vto,
                       "pagado": l.pagado, "anulado": l.anulado} for l in liqs]},
        "pagos": {
            "total": tot_pag, "importe": imp_pag,
            "items": [{"fecha_pago": p.fecha_pago, "no_recibo": p.no_recibo, "origen": p.origen,
                       "bonos": p.bonos, "pesos": p.pesos, "cobrado_total": p.cobrado_total,
                       "premios_pesos": p.premios_pesos, "cajero": p.cajero,
                       "anulado": p.anulado} for p in pagos]},
    }
