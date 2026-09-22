"""Servicios del módulo Créditos: evaluación de solicitudes y otorgamiento.

El otorgamiento genera el plan de cuotas con el motor de dominio (calibrado
contra datos reales) y lo persiste en las tablas `creditos` y `cuotas`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.domain import carteras
from app.domain.cuotas import ParametrosLinea, generar_plan, PlanCuotas
from app.domain.margen import margen_disponible
from app import models

CERO = Decimal("0")


class ReglaNegocioError(Exception):
    """Violación de una regla de negocio (margen, cartera, estado)."""


def parametros_de_linea(linea: models.LineaCredito) -> ParametrosLinea:
    return ParametrosLinea(
        tipo_calculo=linea.tipo_calculo,
        tna=linea.tna,
        iva=linea.iva,
        seguro_pct=linea.seguro_pct,
        gastos_adm_pct=linea.gastos_adm_pct,
        por_afecta=linea.por_afecta,
        cartera=linea.cartera,
    )


def total_afectado(db: Session, cliente_id: int) -> Decimal:
    """Suma de la cuota promedio de los créditos ACTIVOS del cliente.

    Aproxima el haber ya comprometido por descuento de planilla. Se afina cuando
    tengamos la lógica exacta de afectación por cuota vigente del VFP.
    """
    creditos = db.scalars(
        select(models.Credito).where(
            models.Credito.cliente_id == cliente_id,
            models.Credito.estado == "A",
        )
    ).all()
    total = CERO
    for cr in creditos:
        prom = db.scalar(
            select(func.avg(models.Cuota.total)).where(
                models.Cuota.credito_id == cr.id,
                models.Cuota.estado != "P",  # no pagadas
            )
        )
        if prom:
            total += Decimal(prom)
    return total


def evaluar_solicitud(db: Session, solicitud: models.Solicitud) -> dict:
    """Evalúa margen y cartera. Devuelve {plan, margen, puede, advertencias}."""
    cliente = db.get(models.Cliente, solicitud.cliente_id)
    linea = db.get(models.LineaCredito, solicitud.linea_id)
    if not cliente or not linea:
        raise ReglaNegocioError("Cliente o línea inexistentes")

    advertencias: list[str] = []
    params = parametros_de_linea(linea)
    plan: PlanCuotas = generar_plan(
        capital=solicitud.monto_solicitado,
        plazo=solicitud.cantidad_cuotas,
        linea=params,
        fecha_primer_vto=solicitud.fecha_solicitud,
        cuota_fija=(solicitud.cuota_fija or None),
    )

    puede = True
    margen_val: Decimal | None = None
    if carteras.afecta_margen(linea.cartera):
        afectado = total_afectado(db, cliente.id)
        r = margen_disponible(cliente.sueldo, linea.por_afecta, afectado)
        margen_val = r.margen_disponible
        puede = r.puede_tomar_credito
        if not puede:
            advertencias.append("Margen de afectación insuficiente (< 200).")
        elif plan.cuota_promedio > r.margen_disponible:
            advertencias.append(
                "La cuota promedio supera el margen de afectación disponible.")
            puede = False
    else:
        advertencias.append(
            f"Cartera '{carteras.CARTERA_NOMBRE.get(linea.cartera, linea.cartera)}' "
            "no consume margen de afectación.")

    # compatibilidad de cartera con créditos activos del cliente
    activos = db.scalars(
        select(models.Credito).where(
            models.Credito.cliente_id == cliente.id,
            models.Credito.estado == "A",
        )
    ).all()
    for cr in activos:
        sol_prev = db.get(models.Solicitud, cr.solicitud_id)
        if not sol_prev:
            continue
        linea_prev = db.get(models.LineaCredito, sol_prev.linea_id)
        estado = carteras.compatibilidad(linea_prev.cartera, linea.cartera)
        if estado == "bloqueado":
            advertencias.append(
                f"Bloqueado: crédito activo en cartera "
                f"'{carteras.CARTERA_NOMBRE.get(linea_prev.cartera)}' incompatible.")
            puede = False
        elif estado == "previo_pago":
            advertencias.append(
                f"El cliente tiene un crédito activo en la misma cartera "
                f"(N° {cr.id}); podría requerir previo pago.")

    return {"plan": plan, "margen": margen_val, "puede": puede,
            "advertencias": advertencias, "cliente": cliente, "linea": linea}


def otorgar(db: Session, solicitud: models.Solicitud, forzar: bool = False) -> models.Credito:
    """Otorga el crédito: genera y persiste el plan de cuotas.

    `forzar=True` permite otorgar pese a advertencias de margen (decisión de un
    perfil autorizado). El bloqueo por cartera incompatible no se puede forzar.
    """
    if solicitud.estado == "O":
        raise ReglaNegocioError("La solicitud ya fue otorgada.")
    if solicitud.estado == "B":
        raise ReglaNegocioError("La solicitud está dada de baja.")

    ev = evaluar_solicitud(db, solicitud)
    bloqueado = any(a.startswith("Bloqueado") for a in ev["advertencias"])
    if bloqueado:
        raise ReglaNegocioError("; ".join(a for a in ev["advertencias"]
                                          if a.startswith("Bloqueado")))
    if not ev["puede"] and not forzar:
        raise ReglaNegocioError(
            "No se puede otorgar: " + "; ".join(ev["advertencias"]))

    plan: PlanCuotas = ev["plan"]
    credito = models.Credito(
        solicitud_id=solicitud.id,
        linea_id=solicitud.linea_id,
        cliente_id=solicitud.cliente_id,
        capital=solicitud.monto_solicitado,
        saldo_capital=solicitud.monto_solicitado,
        fecha_otorgamiento=date.today(),
        estado="A",
    )
    db.add(credito)
    db.flush()  # obtener credito.id

    for c in plan.cuotas:
        db.add(models.Cuota(
            credito_id=credito.id,
            numero=c.numero,
            fecha_vencimiento=c.vencimiento,
            saldo_capital=c.saldo_capital,
            amortizacion=c.amortizacion,
            interes=c.interes,
            iva_interes=c.iva_interes,
            seguro=c.seguro,
            iva_seguro=c.iva_seguro,
            gastos_adm=c.gastos_adm,
            iva_gastos_adm=c.iva_gastos_adm,
            total=c.total,
            estado="A",
        ))

    solicitud.estado = "O"
    db.flush()
    from app.services import contabilidad, seguros, egresos
    contabilidad.asiento_otorgamiento(db, credito)
    seguros.crear_poliza_si_corresponde(db, credito, ev["linea"])
    egresos.op_desembolso_credito(db, credito, ev["cliente"].apellido_nombre)
    db.commit()
    db.refresh(credito)
    return credito


def dar_baja_credito(db: Session, *, credito_id: int, motivo: str,
                     usuario: str, fecha: date | None = None) -> models.Credito:
    """Baja/anulación administrativa de un crédito (VFP: frm325650000bajacre / menú
    32565). Distinta de la cancelación por pago: **anula** el crédito con un **motivo
    obligatorio** (corrección de errores, etc.). No se puede dar de baja un crédito con
    cuotas ya pagadas (para ésos va la cancelación 32045). Marca estado 'B', anula las
    cuotas pendientes y libera el margen del cliente."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ReglaNegocioError("Debe ingresar un motivo de baja")
    credito = db.get(models.Credito, credito_id)
    if not credito:
        raise ReglaNegocioError("Crédito inexistente")
    if credito.estado == "B":
        raise ReglaNegocioError("El crédito ya está dado de baja")
    if credito.estado == "C":
        raise ReglaNegocioError("El crédito está cancelado; no corresponde baja")
    pagadas = db.scalar(select(func.count()).select_from(models.Cuota).where(
        models.Cuota.credito_id == credito_id, models.Cuota.estado == "P"))
    if pagadas:
        raise ReglaNegocioError(
            "El crédito tiene cuotas pagadas; corresponde cancelación (32045), no baja")
    # anular cuotas pendientes y dar de baja
    for c in db.scalars(select(models.Cuota).where(
            models.Cuota.credito_id == credito_id)).all():
        c.estado = "B"
    credito.estado = "B"
    credito.saldo_capital = Decimal("0")
    credito.motivo_baja = motivo[:120]
    credito.fecha_baja = fecha or date.today()
    credito.usuario_baja = usuario
    db.commit()
    db.refresh(credito)
    return credito


def _add_months(d: date, n: int) -> date:
    """Suma n meses a una fecha, ajustando el día al último válido (equiv. GOMONTH)."""
    import calendar
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def _cuotas_pendientes_recalc(db: Session, credito_id: int):
    """Cuotas recalculables: activas o en mora (estado A/M), nunca pagadas (P) ni de
    baja (B). Ordenadas por número. (VFP: estado $ 'AM')."""
    return db.scalars(select(models.Cuota).where(
        models.Cuota.credito_id == credito_id,
        models.Cuota.estado.in_(("A", "M"))).order_by(models.Cuota.numero)).all()


def recalculo_preview(db: Session, credito_id: int, *, modo: str,
                      primer_vto: date | None = None,
                      haber: Decimal | None = None) -> dict:
    """Vista previa del recálculo (32535) SIN escribir. Dos modos exactos del fuente
    `frm325350000reca`:
      - 'vencimientos' (recaotros, comportamiento ACTIVO en producción): recalcula el
        cronograma con el motor y **sólo reprograma la `fecha_vto`** de las cuotas no
        pagadas (el reescrito de capital/interés está comentado en el fuente).
      - 'jubilatorio' (recaportes): regenera el plan pendiente como **capital puro**
        (interés=0), cuota = 10% del haber jubilatorio; última cuota = resto."""
    credito = db.get(models.Credito, credito_id)
    if not credito:
        raise ReglaNegocioError("Crédito inexistente")
    if credito.estado != "A":
        raise ReglaNegocioError("Sólo se recalculan créditos activos")
    pendientes = _cuotas_pendientes_recalc(db, credito_id)
    if not pendientes:
        raise ReglaNegocioError("El crédito no tiene cuotas activas para recalcular")

    actual = [{"numero": c.numero, "fecha_vto": c.fecha_vencimiento,
               "capital": c.amortizacion, "interes": c.interes, "iva": c.iva_interes,
               "total": c.total} for c in pendientes]

    if modo == "vencimientos":
        if not primer_vto:
            raise ReglaNegocioError("Indicá la fecha de vencimiento de la primera cuota no vencida")
        # el fuente arranca el plan en primer_vto para la cuota Nº1; la cuota Nº N vence
        # a primer_vto + (N-1) meses. Sólo se reprograma la fecha de las pendientes.
        propuesto = [{"numero": c.numero,
                      "fecha_vto": _add_months(primer_vto, c.numero - 1),
                      "capital": c.amortizacion, "interes": c.interes,
                      "iva": c.iva_interes, "total": c.total} for c in pendientes]
    elif modo == "jubilatorio":
        if not haber or Decimal(haber) <= 0:
            raise ReglaNegocioError("Indicá el importe del haber jubilatorio")
        pagadas = db.scalars(select(models.Cuota).where(
            models.Cuota.credito_id == credito_id, models.Cuota.estado == "P")).all()
        tot_pagado = sum((c.total_pagado for c in pagadas), Decimal("0"))
        ultima_pagada = max((c.numero for c in pagadas), default=0)
        saldo = Decimal(credito.capital) - tot_pagado           # VFP: montosol - lntotpag
        cuota = (Decimal(haber) * Decimal("0.10")).quantize(Decimal("0.01"))
        if cuota <= 0:
            raise ReglaNegocioError("La cuota calculada (10% del haber) es cero")
        ncc = int(saldo // cuota)
        resto = saldo - cuota * ncc
        if resto > 0:
            ncc += 1
        # primer vto de las nuevas = el de la primera pendiente, o mes próximo + 10
        base_vto = pendientes[0].fecha_vencimiento or _add_months(date.today(), 1)
        vfvto = base_vto
        propuesto, sdo = [], saldo
        for i in range(1, ncc + 1):
            imp = resto if (i == ncc and resto > 0) else cuota
            propuesto.append({"numero": ultima_pagada + i, "fecha_vto": vfvto,
                              "capital": imp, "interes": Decimal("0.00"),
                              "iva": Decimal("0.00"), "total": imp})
            sdo -= imp
            vfvto = _add_months(vfvto, 1)
    else:
        raise ReglaNegocioError("Modo inválido (vencimientos | jubilatorio)")

    return {"credito_id": credito_id, "modo": modo,
            "cantidad_actual": len(actual), "cantidad_propuesta": len(propuesto),
            "total_actual": sum((x["total"] for x in actual), Decimal("0")),
            "total_propuesto": sum((x["total"] for x in propuesto), Decimal("0")),
            "actual": actual, "propuesto": propuesto}


def recalculo_aplicar(db: Session, credito_id: int, *, modo: str, usuario: str,
                      primer_vto: date | None = None,
                      haber: Decimal | None = None) -> dict:
    """Aplica el recálculo (escribe). Reproduce exactamente el fuente: en
    'vencimientos' sólo cambia fecha_vto de las pendientes; en 'jubilatorio' regenera
    las pendientes como capital puro. Nunca toca cuotas pagadas."""
    prev = recalculo_preview(db, credito_id, modo=modo, primer_vto=primer_vto, haber=haber)
    pendientes = _cuotas_pendientes_recalc(db, credito_id)

    if modo == "vencimientos":
        by_num = {c.numero: c for c in pendientes}
        for p in prev["propuesto"]:
            c = by_num.get(p["numero"])
            if c:
                c.fecha_vencimiento = p["fecha_vto"]
    else:  # jubilatorio: regenerar pendientes como capital puro
        prop = prev["propuesto"]
        # reutilizar las cuotas pendientes existentes; crear/borrar según cantidad
        for idx, p in enumerate(prop):
            if idx < len(pendientes):
                c = pendientes[idx]
            else:
                c = models.Cuota(credito_id=credito_id, numero=p["numero"],
                                 fecha_vencimiento=p["fecha_vto"], saldo_capital=Decimal("0"),
                                 amortizacion=Decimal("0"), interes=Decimal("0"),
                                 iva_interes=Decimal("0"), seguro=Decimal("0"),
                                 iva_seguro=Decimal("0"), gastos_adm=Decimal("0"),
                                 iva_gastos_adm=Decimal("0"), total=Decimal("0"),
                                 total_pagado=Decimal("0"), estado="A")
                db.add(c)
            c.numero = p["numero"]; c.fecha_vencimiento = p["fecha_vto"]
            c.amortizacion = p["capital"]; c.interes = Decimal("0")
            c.iva_interes = Decimal("0"); c.total = p["total"]; c.estado = "A"
        # borrar cuotas pendientes sobrantes (más allá de la nueva cantidad)
        for c in pendientes[len(prop):]:
            db.delete(c)

    db.commit()
    return {"credito_id": credito_id, "modo": modo,
            "cuotas_resultantes": prev["cantidad_propuesta"],
            "total": prev["total_propuesto"]}


def _dias_habiles_periodo(periodo: str, desde: date) -> list[date]:
    """Días hábiles (lun-vie) del período YYYYMM posteriores a `desde`. NOTA: no hay
    tabla de feriados migrada, así que sólo se excluyen fines de semana (el fuente
    excluía además `feriado/feriadon`)."""
    import calendar as _cal
    if len(periodo) != 6 or not periodo.isdigit():
        raise ReglaNegocioError("Período inválido (YYYYMM)")
    anio, mes = int(periodo[:4]), int(periodo[4:])
    if not (1 <= mes <= 12):
        raise ReglaNegocioError("Mes inválido en el período")
    ndias = _cal.monthrange(anio, mes)[1]
    dias = []
    for d in range(1, ndias + 1):
        f = date(anio, mes, d)
        if f.weekday() < 5 and f > desde:   # lun-vie y futuro (VFP: DATE()+1 < fecha)
            dias.append(f)
    return dias


def generar_turnos_preview(db: Session, *, periodo: str, cantidad: int,
                           grupo: str = "TODO", desde: date | None = None) -> dict:
    """Vista previa de la generación de turnos del mes (VFP: frm320700000turnosnuevo /
    menú 32065). Distribuye `cantidad` turnos entre los días hábiles: por día =
    INT(cantidad/díashábiles); el resto (cantidad % días) se reparte de a uno en los
    primeros días. No escribe."""
    if cantidad <= 0:
        raise ReglaNegocioError("La cantidad de turnos debe ser positiva")
    desde = desde or date.today()
    dias = _dias_habiles_periodo(periodo, desde)
    if not dias:
        raise ReglaNegocioError("No hay días hábiles futuros en el período")
    existentes = db.scalar(select(func.count()).select_from(models.TurnoCredito).where(
        models.TurnoCredito.periodo == periodo, models.TurnoCredito.tipo == grupo))
    por_dia = cantidad // len(dias)
    resto = cantidad % len(dias)
    dist, n = [], 0
    for i, f in enumerate(dias):
        cant = por_dia + (1 if i < resto else 0)
        if cant:
            dist.append({"fecha": f, "cantidad": cant})
            n += cant
    return {"periodo": periodo, "grupo": grupo, "dias_habiles": len(dias),
            "turnos_por_dia": por_dia, "resto": resto, "total": n,
            "ya_existen": existentes, "distribucion": dist}


def generar_turnos_aplicar(db: Session, *, periodo: str, cantidad: int, usuario: str,
                           grupo: str = "TODO", desde: date | None = None) -> dict:
    """Genera y persiste los turnos del período (32065). Rechaza si ya hay turnos del
    período/grupo (para no duplicar)."""
    prev = generar_turnos_preview(db, periodo=periodo, cantidad=cantidad,
                                  grupo=grupo, desde=desde)
    if prev["ya_existen"]:
        raise ReglaNegocioError(
            f"Ya existen {prev['ya_existen']} turnos del período {periodo} (grupo {grupo})")
    n = 0
    for dia in prev["distribucion"]:
        for _ in range(dia["cantidad"]):
            n += 1
            db.add(models.TurnoCredito(tipo=grupo, numero=n, periodo=periodo,
                                       fecha=dia["fecha"], usado=False, autorizado=True))
    db.commit()
    return {"periodo": periodo, "grupo": grupo, "generados": n}


def asignar_turno(db: Session, *, periodo: str, cuil: str, apellido_nombre: str,
                  linea: int = 0, sueldo: Decimal | None = None,
                  numero: int | None = None) -> models.TurnoCredito:
    """Asigna un turno a un solicitante (VFP: frm320720000clienteturno / 32067). Toma
    el próximo turno libre del período (o el `numero` puntual para turnos excepcionales,
    32068) y le carga los datos de la persona."""
    if not (cuil or "").strip():
        raise ReglaNegocioError("Indicá el CUIL del solicitante")
    q = select(models.TurnoCredito).where(
        models.TurnoCredito.periodo == periodo, models.TurnoCredito.usado.is_(False),
        models.TurnoCredito.cuil == "")
    if numero is not None:
        q = q.where(models.TurnoCredito.numero == numero)
    turno = db.scalars(q.order_by(models.TurnoCredito.numero)).first()
    if not turno:
        raise ReglaNegocioError("No hay turnos disponibles para ese período"
                                + (f" (N° {numero})" if numero is not None else ""))
    turno.cuil = cuil.strip()
    turno.apellido_nombre = (apellido_nombre or "").strip()[:80]
    turno.linea = linea or 0
    turno.sueldo = Decimal(sueldo) if sueldo is not None else Decimal("0")
    db.commit()
    db.refresh(turno)
    return turno
