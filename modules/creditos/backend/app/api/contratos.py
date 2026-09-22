"""Originación y servicing de contratos de préstamo (Configurar Créditos, Fases 5 y 6).

Fase 5: ofrecer al cliente sólo productos PUBLICADOS y originar un contrato que congela
el snapshot del producto y su cronograma. Fase 6: registrar actividades (pago, prepago,
payoff, cambio de tasa) sobre el contrato.
"""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.reports.pdf import contrato_pdf
from app.reports.excel import contratos_pp_excel

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

from app.core import configuraciones as config
from app.core.database import get_db
from app.core.numbering import crear_con_numero_unico
from app.core.idempotency import con_idempotencia
from app.core.permisos import requiere_permiso
from app.deps import get_current_user
from app import models, models_productos as m
from app.services import auditoria as audit
from app.services.productos_calc import cronograma
from app.api.productos import (_serial, _serial_efectivo, _version_efectiva,
                               _calc_codigo_por_version, _ultima, _tasa, _tna_base, _cargo,
                               _disponibilidad, _elegibilidad, SEGMENTOS_CATALOGO, canales_catalogo,
                               canal_backoffice, decimales_calculo, decimales_mostrar,
                               RELACION_PRICING, _bonus_relacion, _contab_cfg, _params_cronograma,
                               _feriados_engine)
from app.services import contabilidad as cont

router = APIRouter(prefix="/api/creditos/contratos", tags=["contratos"],
                   dependencies=[Depends(get_current_user)])


class OriginarIn(BaseModel):
    producto_id: str
    cliente_nombre: str
    monto: float
    plazo: int
    tasa: float | None = None   # tasa negociada (sólo si el producto la permite)
    # Perfil del solicitante (Fase E — disponibilidad/segmentación). Opcional.
    segmento: str | None = None
    canal: str | None = None
    edad: int | None = None
    antiguedad_meses: int | None = None
    relacion: str | None = None   # relationship pricing (Fase G): ESTANDAR|PREFERENCIAL|PREMIUM
    solicitud_id: int | None = None   # origen: solicitud de crédito legacy (VFP) aprobada
    solicitud_pp_id: str | None = None  # origen: solicitud nueva (pp_solicitud) APROBADA
    datos_adicionales: dict = {}      # destino, CBU de acreditación, garante, observaciones
    desembolsar: bool = True          # False = otorgar y dejar A_LIQUIDAR (desembolso en paso aparte)


def _ctx(segmento=None, canal=None, edad=None, antiguedad_meses=None) -> dict:
    return {"segmento": segmento, "canal": canal, "edad": edad, "antiguedad_meses": antiguedad_meses}


def _liquidacion(monto: float, cargo_otorg_pct: float, params: dict) -> dict:
    """Liquidación del desembolso, consistente con el motor (única fuente de verdad).

    El cliente recibe el monto completo: los cargos NO se deducen del acreditado, ya están dentro
    del cronograma (financiados al capital, prorrateados o cobrados en la 1ª cuota). Antes se
    restaban del neto y además se cobraban en la cuota → doble cobro (corregido, H-085).
    """
    fin = bool(params.get("financiable"))
    otorg = monto * (float(cargo_otorg_pct) / 100)
    financiado = otorg if fin else 0.0     # va al capital y se amortiza
    en_cuotas = 0.0 if fin else otorg      # prorrateado o cobrado en la 1ª cuota
    for c in params.get("cargos") or []:
        val = monto * (float(c.get("porcentaje") or 0) / 100)
        es_prorr = str(c.get("momento") or "PRORRATEADO").upper() == "PRORRATEADO"
        if fin and not es_prorr:
            financiado += val
        else:
            en_cuotas += val
    return {"monto": round(monto, 2),
            "cargosFinanciados": round(financiado, 2),   # sumados al capital
            "cargosEnCuotas": round(en_cuotas, 2),        # cobrados dentro de las cuotas
            "capitalAmortizar": round(monto + financiado, 2),
            "neto": round(monto, 2)}                       # el cliente recibe el monto completo


def _overdue_cfg(v: m.PPVersion) -> dict:
    """Config del componente OVERDUE (mora) de la versión, o {} si no está activo."""
    for c in v.componentes:
        if c.componente_codigo == "OVERDUE" and c.activo:
            return c.config or {}
    return {}


def _mora_de_cuota(c: m.PPContrato, cuota, fecha) -> tuple[Decimal, Decimal, int]:
    """Punitorio (interés + IVA) e IVA de una cuota vencida pagada en `fecha`.

    Reutiliza el calculador legacy (`domain.mora`): int_pun = cuota · tasa_diaria · días.
    La tasa punitoria diaria = moraTNA/365. Descuenta los días de gracia del producto (congelados
    en el snapshot). Si no hay atraso neto, devuelve 0.
    """
    from app.domain.mora import calcular_mora
    _dec = lambda x: Decimal(str(x or 0))
    snap = c.snapshot_producto or {}
    mora_tna = float(snap.get("mora_tna") or 0)
    gracia = int(snap.get("dias_gracia_mora") or 0)
    if mora_tna <= 0 or cuota.fecha_vencimiento is None:
        return Decimal(0), Decimal(0), 0
    dias = (fecha - cuota.fecha_vencimiento).days - gracia
    if dias <= 0:
        return Decimal(0), Decimal(0), 0
    r = calcular_mora(cuota=_dec(cuota.total), saldo=_dec(c.saldo_capital or 0), dias=dias,
                      tasa_punitoria_diaria=Decimal(str(mora_tna / 365)))
    return r.interes_punitorio, r.iva_punitorio, dias


class ActividadIn(BaseModel):
    tipo: str            # PAYMENT | PAYOFF | RATE_CHANGE | PARTIAL_PREPAYMENT
    importe: float = 0
    detalle: str = ""
    fecha: str | None = None   # fecha valor (backdating): ISO date; por defecto hoy
    modo: str = "BAJA_PLAZO"   # prepago: BAJA_PLAZO (misma cuota) | BAJA_CUOTA (mismo plazo)
    medio_pago: str = ""       # caja: EFECTIVO | TRANSFERENCIA | DEBITO | CHEQUE (para el recibo)
    cuotas: int = 1            # adelanto: cantidad de cuotas a pagar de una (PAYMENT)


def _fmt(v) -> float:
    return float(v) if v is not None else 0.0


def _proximo_numero_contrato(db: Session, anio: int) -> str:
    """Primer CTO-{anio}-NNNNN libre. Usar count() global colisiona con la constraint única
    cuando se borran contratos o al cruzar de año (mismo bug que H-097 en las líneas)."""
    pref = f"CTO-{anio}-"
    usados = {x for (x,) in db.query(m.PPContrato.numero_contrato)
              .filter(m.PPContrato.numero_contrato.like(f"{pref}%")).all()}
    n = 1
    while f"{pref}{n:05d}" in usados:
        n += 1
    return f"{pref}{n:05d}"


def _serial_contrato(c: m.PPContrato, db: Session | None = None) -> dict:
    out = {
        "id": c.id, "numero_contrato": c.numero_contrato, "cliente_nombre": c.cliente_nombre,
        "producto_id": c.producto_id, "version": c.producto_version_numero, "sistema": c.sistema,
        "monto_original": _fmt(c.monto_original), "saldo_capital": _fmt(c.saldo_capital),
        "plazo": c.plazo, "tasa": _fmt(c.tasa_contratada), "estado": c.estado,
        "fecha_valor": str(c.fecha_valor), "fecha_vencimiento": str(c.fecha_vencimiento),
        "snapshot": c.snapshot_producto, "solicitud_origen": c.solicitud_origen,
        "datos_adicionales": c.datos_adicionales or {},
        "liquidacion": (c.snapshot_producto or {}).get("liquidacion"),
        "cuotas": [{
            "numero_cuota": q.numero_cuota, "fecha_vencimiento": str(q.fecha_vencimiento),
            "estado": q.estado, "saldo_inicial": _fmt(q.saldo_inicial), "capital": _fmt(q.capital),
            "interes": _fmt(q.interes), "cargos": _fmt(q.cargos), "impuestos": _fmt(q.impuestos),
            "total": _fmt(q.total), "saldo_final": _fmt(q.saldo_final), "pagado": _fmt(q.pagado),
            "devengada": bool(q.devengada),
        } for q in sorted(c.cuotas, key=lambda x: x.numero_cuota)],
        "actividades": [{
            "id": a.id, "tipo": a.tipo, "fecha": str(a.fecha), "importe": _fmt(a.importe),
            "estado": a.estado, "detalle": a.detalle, "por": a.creado_por,
            "reversaDe": a.reversa_de, "dato": a.dato,
        } for a in sorted(c.actividades, key=lambda x: (x.fecha, x.creado_en))],
        "asientos": [],
    }
    if db is not None:
        asientos = db.query(models.Asiento).filter(
            models.Asiento.concepto.like(f"%{c.numero_contrato}%")).order_by(models.Asiento.id).all()
        out["asientos"] = [{
            "id": a.id, "fecha": str(a.fecha), "concepto": a.concepto, "origen": a.origen,
            "lineas": [{"cuenta": l.cuenta_codigo, "nombre": l.cuenta_nombre,
                        "debe": _fmt(l.debe), "haber": _fmt(l.haber)} for l in a.lineas],
        } for a in asientos]
    return out


@router.get("/segmentos")
def segmentos(db: Session = Depends(get_db)):
    """Catálogo de segmentos/canales (Fase E) y relaciones/relationship pricing (Fase G).
    Los canales salen de Parámetros (configurable), no de una lista hardcodeada — H-185."""
    return {"segmentos": SEGMENTOS_CATALOGO, "canales": canales_catalogo(db),
            "canalBackoffice": canal_backoffice(db),
            "decimalesCalculo": decimales_calculo(db), "decimalesMostrar": decimales_mostrar(db),
            "relaciones": [{"codigo": k, "bonusTna": v} for k, v in RELACION_PRICING.items()]}


@router.get("/solicitudes")
def solicitudes_aprobadas(q: str | None = None, estado: str = "A", limit: int = 30,
                          db: Session = Depends(get_db)):
    """Solicitudes de crédito legacy (VFP) aprobadas y aún no originadas como contrato pp."""
    usadas = {sid for (sid,) in db.query(m.PPContrato.solicitud_origen)
              .filter(m.PPContrato.solicitud_origen.isnot(None)).all()}
    qy = db.query(models.SolicitudCredito).filter(
        models.SolicitudCredito.estado == estado,
        models.SolicitudCredito.apellido_nombre != "",
        models.SolicitudCredito.montosol > 0)
    if q:
        like = f"%{q.strip()}%"
        qy = qy.filter(models.SolicitudCredito.apellido_nombre.ilike(like)
                       | models.SolicitudCredito.cuil.ilike(like))
    filas, out = qy.order_by(models.SolicitudCredito.id.desc()).limit(limit * 2).all(), []
    for s in filas:
        if s.id in usadas:
            continue
        out.append({"id": s.id, "apellido_nombre": s.apellido_nombre, "cuil": s.cuil,
                    "dni": s.dni, "monto": _fmt(s.montosol), "linea": s.linea,
                    "fecha": str(s.fecha_soli) if s.fecha_soli else ""})
        if len(out) >= limit:
            break
    return {"items": out, "total": len(out)}


@router.get("/bundles")
def bundles(db: Session = Depends(get_db)):
    """Paquetes de productos (Fase G): bundle + sus miembros (líneas publicadas)."""
    calc_map = _calc_codigo_por_version(db)
    out = []
    for b in db.query(m.PPBundle).filter_by(activo=True).all():
        miembros = []
        for it in sorted(b.items, key=lambda x: x.orden):
            prod = db.get(m.PPProducto, it.producto_id)
            if not prod:
                continue
            # Mostrar la versión VIGENTE del miembro (consistente con la oferta), no un borrador.
            miembros.append({"rol": it.rol, "obligatorio": it.obligatorio,
                             "producto": _serial_efectivo(db, prod, calc_map)})
        out.append({"id": b.id, "codigo": b.codigo, "nombre": b.nombre,
                    "descripcion": b.descripcion, "miembros": miembros})
    return {"items": out, "total": len(out)}


@router.get("/tablero")
def tablero(db: Session = Depends(get_db)):
    """Tablero de cartera profesional: KPIs, mora/aging por tramo, evolución mensual, desgloses por
    estado/producto y el detalle de contratos (con días de atraso) para el drill-down del front."""
    contratos = db.query(m.PPContrato).all()
    hoy = date.today()
    ym = lambda d: f"{d.year:04d}-{d.month:02d}"

    # Cobranza EJECUTADA (para recaudación del mes y la evolución mensual).
    PAGO_TIPOS = ("PAYMENT", "PAYOFF", "PARTIAL_PREPAYMENT")
    acts = (db.query(m.PPActividad)
            .filter(m.PPActividad.estado == "EJECUTADA", m.PPActividad.tipo.in_(PAGO_TIPOS)).all())
    cobrado_mes: dict[str, Decimal] = {}
    recaudado_mes = Decimal(0)
    for a in acts:
        cobrado_mes[ym(a.fecha)] = cobrado_mes.get(ym(a.fecha), Decimal(0)) + (a.importe or Decimal(0))
        if a.fecha.year == hoy.year and a.fecha.month == hoy.month:
            recaudado_mes += a.importe or Decimal(0)

    AGING = ["Al día", "1–30", "31–60", "61–90", "90+"]
    aging = {b: {"contratos": 0, "saldo": Decimal(0)} for b in AGING}
    por_estado: dict[str, dict] = {}
    por_prod: dict[str, dict] = {}
    orig_mes: dict[str, dict] = {}

    capital = saldo_vig = cobrado_tot = mora_monto = tna_pond = Decimal(0)
    plazo_tot = cuotas_pag = cuotas_pend = en_mora = vencen30_n = 0
    vencen30_monto = Decimal(0)
    detalle: list[dict] = []

    for c in contratos:
        snap = c.snapshot_producto or {}
        activo = c.estado == "ACTIVO"
        sc = c.saldo_capital or Decimal(0)
        mo = c.monto_original or Decimal(0)
        capital += mo
        plazo_tot += c.plazo or 0
        pe = por_estado.setdefault(c.estado, {"contratos": 0, "capital": Decimal(0), "saldo": Decimal(0)})
        pe["contratos"] += 1; pe["capital"] += mo
        if activo:
            saldo_vig += sc; pe["saldo"] += sc; tna_pond += (c.tasa_contratada or Decimal(0)) * sc
        if c.fecha_valor:
            om = orig_mes.setdefault(ym(c.fecha_valor), {"monto": Decimal(0), "n": 0})
            om["monto"] += mo; om["n"] += 1
        # Mora / aging / próximos vencimientos (por cuotas).
        min_venc = None
        for q in c.cuotas:
            if q.estado == "PAGADA":
                cuotas_pag += 1; cobrado_tot += q.pagado or Decimal(0)
            else:
                cuotas_pend += 1
                if q.fecha_vencimiento < hoy:
                    min_venc = q.fecha_vencimiento if (min_venc is None or q.fecha_vencimiento < min_venc) else min_venc
                elif q.fecha_vencimiento <= hoy + timedelta(days=30):
                    vencen30_monto += q.total or Decimal(0); vencen30_n += 1
        dias = (hoy - min_venc).days if (activo and min_venc) else 0
        bucket = "Al día"
        if activo and dias > 0:
            bucket = "1–30" if dias <= 30 else "31–60" if dias <= 60 else "61–90" if dias <= 90 else "90+"
            en_mora += 1; mora_monto += sc
        if activo:
            aging[bucket]["contratos"] += 1; aging[bucket]["saldo"] += sc
        pd = por_prod.setdefault(c.producto_id, {"id": c.producto_id, "codigo": snap.get("codigo", ""),
              "nombre": snap.get("producto", "") or c.producto_id, "contratos": 0,
              "capital": Decimal(0), "saldo": Decimal(0), "mora": Decimal(0)})
        pd["contratos"] += 1; pd["capital"] += mo
        if activo:
            pd["saldo"] += sc
            if dias > 0:
                pd["mora"] += sc
        prox = next((q for q in sorted(c.cuotas, key=lambda x: x.numero_cuota) if q.estado != "PAGADA"), None)
        detalle.append({
            "id": c.id, "numero": c.numero_contrato, "cliente": c.cliente_nombre,
            "productoId": c.producto_id, "producto": snap.get("producto", ""), "codigo": snap.get("codigo", ""),
            "estado": c.estado, "sistema": c.sistema, "monto": _fmt(mo), "saldo": _fmt(sc),
            "tna": _fmt(c.tasa_contratada), "plazo": c.plazo, "diasAtraso": dias, "moraBucket": bucket,
            "fechaAlta": str(c.fecha_valor) if c.fecha_valor else "",
            "proxVenc": str(prox.fecha_vencimiento) if prox else "",
            "proxCuota": prox.numero_cuota if prox else None,
        })

    n = len(contratos)
    activos = por_estado.get("ACTIVO", {}).get("contratos", 0)
    a_liq = por_estado.get("A_LIQUIDAR", {})
    # Evolución: últimos 6 meses (originación vs cobranza).
    seq: list[str] = []
    yy, mm = hoy.year, hoy.month
    for i in range(5, -1, -1):
        m2, y2 = mm - i, yy
        while m2 <= 0:
            m2 += 12; y2 -= 1
        seq.append(f"{y2:04d}-{m2:02d}")
    evolucion = [{"mes": k, "originadoMonto": _fmt(orig_mes.get(k, {}).get("monto", 0)),
                  "originadoN": orig_mes.get(k, {}).get("n", 0), "cobradoMonto": _fmt(cobrado_mes.get(k, 0))}
                 for k in seq]

    kpis = {
        "contratos": n, "activos": activos,
        "aLiquidarN": a_liq.get("contratos", 0), "aLiquidarMonto": _fmt(a_liq.get("capital", 0)),
        "capitalColocado": _fmt(capital), "saldoVigente": _fmt(saldo_vig), "cobrado": _fmt(cobrado_tot),
        "ticketPromedio": _fmt(capital / n) if n else 0,
        "plazoPromedio": round(plazo_tot / n, 1) if n else 0,
        "tnaPromedioPond": round(float(tna_pond / saldo_vig), 2) if saldo_vig else 0,
        "moraMonto": _fmt(mora_monto),
        "moraPct": round(float(mora_monto / saldo_vig * 100), 1) if saldo_vig else 0,
        "contratosEnMora": en_mora,
        "moraPctContratos": round(en_mora / activos * 100, 1) if activos else 0,
        "recaudadoMes": _fmt(recaudado_mes),
        "vencen30Monto": _fmt(vencen30_monto), "vencen30Cuotas": vencen30_n,
        "cuotasPagadas": cuotas_pag, "cuotasPendientes": cuotas_pend,
    }
    return {
        "generadoEn": str(hoy),
        "kpis": kpis,
        "porEstado": sorted([{"estado": k, "contratos": v["contratos"], "capital": _fmt(v["capital"]),
                              "saldo": _fmt(v["saldo"])} for k, v in por_estado.items()],
                            key=lambda x: x["saldo"], reverse=True),
        "aging": [{"bucket": b, "contratos": aging[b]["contratos"], "saldo": _fmt(aging[b]["saldo"])} for b in AGING],
        "porProducto": sorted([{"id": v["id"], "codigo": v["codigo"], "nombre": v["nombre"],
                                "contratos": v["contratos"], "capital": _fmt(v["capital"]), "saldo": _fmt(v["saldo"]),
                                "mora": _fmt(v["mora"]),
                                "moraPct": round(float(v["mora"] / v["saldo"] * 100), 1) if v["saldo"] else 0}
                               for v in por_prod.values()], key=lambda x: x["saldo"], reverse=True),
        "evolucion": evolucion,
        "contratos": detalle,
        # Compat con claves antiguas.
        "contratosTotal": n, "capitalColocado": _fmt(capital), "saldoVigente": _fmt(saldo_vig),
        "cobrado": _fmt(cobrado_tot), "contratosEnMora": en_mora,
    }


@router.get("/oferta")
def oferta(db: Session = Depends(get_db),
           segmento: str | None = None, canal: str | None = None,
           edad: int | None = None, antiguedad_meses: int | None = None,
           solo_elegibles: bool = False):
    """Catálogo ofrecible al cliente: sólo versiones PUBLICADAS.

    Fase E: cada ítem se anota con `elegibilidad` (elegible + motivos) evaluada contra el
    perfil del solicitante. Con `solo_elegibles=true` se devuelven sólo los elegibles.
    """
    ctx = _ctx(segmento, canal, edad, antiguedad_meses)
    calc_map = _calc_codigo_por_version(db)
    items = []
    for p in db.query(m.PPProducto).all():
        v = _version_efectiva(p)   # la versión VIGENTE por fecha (no un borrador nuevo)
        if v.estado != "PUBLICADO":
            continue
        disp = _disponibilidad(v)
        # Filtro DURO de canal (H-185): si el operador origina por un canal y el producto declara canales
        # que no lo incluyen (p. ej. un producto "solo WEB" y el operador está en SUCURSAL), el producto NO
        # se lista en la oferta del backoffice — no alcanza con marcarlo no elegible. Sin canal, catálogo full.
        if canal:
            canales = [str(x).upper() for x in (disp or {}).get("canales", [])]
            if canales and canal.upper() not in canales:
                continue
        it = _serial_efectivo(db, p, calc_map)   # ofrece las condiciones de la versión vigente
        it["elegibilidad"] = _elegibilidad(disp, ctx)
        if solo_elegibles and not it["elegibilidad"]["elegible"]:
            continue
        items.append(it)
    return {"items": sorted(items, key=lambda x: x["nombre"]), "total": len(items)}


@router.get("")
def listar(db: Session = Depends(get_db)):
    cs = db.query(m.PPContrato).order_by(m.PPContrato.creado_en.desc()).all()
    return {"items": [_serial_contrato(c) for c in cs], "total": len(cs)}


@router.get("/export.xlsx")
def exportar_cartera(db: Session = Depends(get_db)):
    """Exporta la cartera de contratos a Excel."""
    cs = db.query(m.PPContrato).order_by(m.PPContrato.creado_en.desc()).all()
    xlsx = contratos_pp_excel([_serial_contrato(c) for c in cs])
    return Response(content=xlsx, media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="cartera_creditos.xlsx"'})


@router.get("/situacion")
def situacion_cliente(q: str = Query("", min_length=0), db: Session = Depends(get_db),
                      user: models.Usuario = Depends(requiere_permiso("/creditos/situacion-linea", "CONSULTA"))):
    """Situación de un cliente: sus contratos de crédito (línea nueva) + resumen consolidado.

    Busca por nombre de cliente (parcial, sin distinguir mayúsculas). Devuelve, por contrato,
    saldo, próxima cuota, mora al día, estado y cuotas pagadas/pendientes; y totales del cliente.
    """
    hoy = date.today()
    qry = db.query(m.PPContrato)
    if q:
        qry = qry.filter(m.PPContrato.cliente_nombre.ilike(f"%{q}%"))
    contratos = qry.order_by(m.PPContrato.creado_en.desc()).all()
    items = []
    tot_saldo = tot_colocado = Decimal(0)
    activos = en_mora = 0
    for c in contratos:
        cuotas = sorted(c.cuotas, key=lambda x: x.numero_cuota)
        pend = [x for x in cuotas if x.estado == "PENDIENTE"]
        prox = next((x for x in pend if (x.total or 0) > 0), None)
        vencida = any(x.fecha_vencimiento and x.fecha_vencimiento < hoy for x in pend)
        mora_ip = mora_iv = Decimal(0)
        if prox and c.estado == "ACTIVO":
            mora_ip, mora_iv, _ = _mora_de_cuota(c, prox, hoy)
        tot_colocado += c.monto_original or Decimal(0)
        if c.estado == "ACTIVO":
            tot_saldo += c.saldo_capital or Decimal(0); activos += 1
            if vencida:
                en_mora += 1
        items.append({
            "id": c.id, "numero": c.numero_contrato, "cliente": c.cliente_nombre,
            "sistema": c.sistema, "estado": c.estado, "monto": _fmt(c.monto_original),
            "saldo": _fmt(c.saldo_capital), "plazo": c.plazo, "tasa": _fmt(c.tasa_contratada),
            "fechaAlta": str(c.fecha_valor), "cuotasPagadas": len([x for x in cuotas if x.estado == "PAGADA"]),
            "cuotasPendientes": len(pend),
            "proximaCuota": ({"numero": prox.numero_cuota, "vencimiento": str(prox.fecha_vencimiento),
                              "total": _fmt(prox.total), "pagado": _fmt(prox.pagado)} if prox else None),
            "moraAlDia": _fmt(mora_ip + mora_iv), "enMora": bool(vencida and c.estado == "ACTIVO"),
        })
    return {"items": items,
            "resumen": {"contratos": len(contratos), "activos": activos, "enMora": en_mora,
                        "capitalColocado": _fmt(tot_colocado), "saldoVigente": _fmt(tot_saldo)}}


# ----------------------- Liquidación de préstamos por lote (H-135) -----------------------
# Post-originación: los contratos quedan A_LIQUIDAR. Se agrupan por DÍA de originación (fecha_valor)
# y se liquidan JUNTOS (lote) para pasar a desembolso. Debe declararse ANTES de GET /{contrato_id}
# (si no, "lotes-liquidacion" se interpretaría como un id de contrato).
@router.get("/lotes-liquidacion")
def lotes_liquidacion(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Contratos pendientes de liquidar (A_LIQUIDAR) agrupados por día de originación, del más reciente."""
    rows = (db.query(m.PPContrato).filter(m.PPContrato.estado == "A_LIQUIDAR")
            .order_by(m.PPContrato.fecha_valor.desc(), m.PPContrato.numero_contrato).all())
    # Contratos que ya intentaron liquidarse y esperan la aprobación del workflow DESEMBOLSO.
    pend_ids = {p.contrato_id for p in db.query(m.PPWorkflowPendiente)
                .filter(m.PPWorkflowPendiente.objeto == "DESEMBOLSO",
                        m.PPWorkflowPendiente.estado == "PENDIENTE").all()}
    lotes: dict[str, dict] = {}
    for c in rows:
        k = str(c.fecha_valor)
        lote = lotes.setdefault(k, {"fecha": k, "cantidad": 0, "montoTotal": 0.0, "pendientes": 0, "contratos": []})
        pendiente = c.id in pend_ids
        lote["cantidad"] += 1
        lote["montoTotal"] += float(c.monto_original or 0)
        if pendiente:
            lote["pendientes"] += 1
        lote["contratos"].append({"id": c.id, "numero": c.numero_contrato, "cliente": c.cliente_nombre,
                                  "producto": (c.snapshot_producto or {}).get("producto", ""),
                                  "monto": float(c.monto_original or 0), "plazo": c.plazo,
                                  "pendienteAprobacion": pendiente})
    return {"items": sorted(lotes.values(), key=lambda x: x["fecha"], reverse=True)}


class LiquidarLoteIn(BaseModel):
    fecha: str          # día de originación (YYYY-MM-DD) cuyo lote se liquida


@router.post("/liquidar-lote")
def liquidar_lote(data: LiquidarLoteIn, db: Session = Depends(get_db),
                  user: models.Usuario = Depends(get_current_user),
                  idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Liquida (desembolsa) TODOS los contratos A_LIQUIDAR originados el día indicado. Respeta el
    workflow DESEMBOLSO: los que requieran aprobación quedan pendientes; el resto se desembolsa.
    Idempotente + serializado (H-154): un reintento/doble-clic no desembolsa dos veces, y ante
    concurrencia cada contrato se toma con lock + recheck de estado (la DB es árbitro)."""
    try:
        d = date.fromisoformat(data.fecha)
    except ValueError:
        raise HTTPException(422, "Fecha inválida (se espera YYYY-MM-DD).")

    def _do():
        contratos = (db.query(m.PPContrato)
                     .filter(m.PPContrato.estado == "A_LIQUIDAR", m.PPContrato.fecha_valor == d)
                     .order_by(m.PPContrato.numero_contrato).all())
        if not contratos:
            raise HTTPException(404, "No hay contratos por liquidar para ese día.")
        ids = [c.id for c in contratos]
        desembolsados, pendientes, errores = [], [], []
        for cid in ids:
            try:
                # Tomar el contrato con lock y RE-CHEQUEAR estado dentro de la transacción: dos lotes
                # concurrentes (o doble clic) no lo desembolsan dos veces — el segundo lo ve ya ACTIVO y
                # lo saltea. En Postgres with_for_update serializa; en SQLite el recheck igual protege.
                c = db.query(m.PPContrato).filter_by(id=cid).with_for_update().first()
                if c is None or c.estado != "A_LIQUIDAR":
                    continue                              # otro proceso ya lo liquidó
                gate = _gate_workflow(db, "DESEMBOLSO", c, {}, user)
                if gate is not None:                      # el workflow lo dejó pendiente de aprobación
                    db.commit(); pendientes.append(c.numero_contrato); continue
                _desembolsar(db, c, user); db.commit()
                desembolsados.append(c.numero_contrato)
            except HTTPException as e:
                db.rollback(); errores.append({"contrato": cid, "detalle": str(e.detail)})
        return {"fecha": data.fecha, "total": len(ids), "desembolsados": desembolsados,
                "pendientesAprobacion": pendientes, "errores": errores}

    return con_idempotencia(db, idempotency_key, f"POST /api/contratos/liquidar-lote {data.fecha}",
                            _do, usuario=user.username)


@router.get("/{contrato_id}")
def obtener(contrato_id: str, db: Session = Depends(get_db)):
    c = db.get(m.PPContrato, contrato_id)
    if not c:
        raise HTTPException(404, "Contrato no encontrado")
    return _serial_contrato(c, db)


@router.get("/{contrato_id}/pdf")
def contrato_pdf_endpoint(contrato_id: str, db: Session = Depends(get_db)):
    """Contrato + cronograma en PDF."""
    c = db.get(m.PPContrato, contrato_id)
    if not c:
        raise HTTPException(404, "Contrato no encontrado")
    pdf = contrato_pdf(_serial_contrato(c, db))
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{c.numero_contrato}.pdf"'})


@router.post("/originar", status_code=201)
def originar(data: OriginarIn, request: Request, db: Session = Depends(get_db),
             user: models.Usuario = Depends(get_current_user),
             idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    # Idempotencia de operación: un reintento con la misma Idempotency-Key no origina dos contratos.
    ip = audit.ip_de(request)
    resumen = {"producto_id": data.producto_id, "cliente": data.cliente_nombre,
               "monto": data.monto, "plazo": data.plazo, "tasa": data.tasa}
    try:
        res = con_idempotencia(db, idempotency_key, "POST /api/contratos/originar",
                               lambda: _originar_impl(db, data, user), user.username)
    except HTTPException as e:
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Contrato", operacion="ORIGINAR", resultado="RECHAZADO",
                               despues=resumen, detalle=f"Originación rechazada: {e.detail}")
        raise
    if isinstance(res, dict) and res.get("pendiente"):
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Contrato", entidad_id=res.get("contrato", ""),
                               operacion="ORIGINAR", resultado="RECHAZADO", despues=resumen,
                               detalle=res.get("mensaje", "Pendiente de aprobación (workflow)"))
    else:
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Contrato", entidad_id=(res or {}).get("id", ""),
                               operacion="ORIGINAR", resultado="OK",
                               despues={**resumen, "numero_contrato": (res or {}).get("numero_contrato"),
                                        "estado": (res or {}).get("estado")},
                               detalle=f"Contrato originado #{(res or {}).get('numero_contrato', '')}")
    return res


def _originar_impl(db: Session, data: OriginarIn, user) -> dict:
    prod = db.get(m.PPProducto, data.producto_id)
    if not prod:
        raise HTTPException(404, "Producto no encontrado")
    # Origen legacy (opcional): solicitud de crédito aprobada aún no originada.
    if data.solicitud_id is not None:
        sol = db.get(models.SolicitudCredito, data.solicitud_id)
        if not sol:
            raise HTTPException(404, "Solicitud legacy no encontrada.")
        if db.query(m.PPContrato).filter_by(solicitud_origen=data.solicitud_id).first():
            raise HTTPException(409, "La solicitud ya fue originada como contrato.")
    sol_pp = None
    if data.solicitud_pp_id is not None:
        sol_pp = db.get(m.PPSolicitud, data.solicitud_pp_id)
        if not sol_pp:
            raise HTTPException(404, "Solicitud no encontrada.")
        if sol_pp.estado == "ORIGINADA" or sol_pp.contrato_id:
            raise HTTPException(409, "La solicitud ya fue originada como contrato.")
        if sol_pp.estado != "APROBADA":
            raise HTTPException(409, "Sólo se puede originar una solicitud APROBADA.")
        # Canal web: la originación es una REVISIÓN. No se libera la liquidación si faltan los datos
        # obligatorios (identidad + CBU de acreditación) — H-134. Lazy import: evita ciclo con solicitudes.
        from app.api.solicitudes import _datos_liquidacion
        dl = _datos_liquidacion(db, sol_pp)
        if dl["aplica"] and not dl["lista"]:
            raise HTTPException(422, "Faltan datos para liquidar el crédito: " + ", ".join(dl["faltantes"])
                                + ". Completá la revisión de la solicitud antes de originar.")
    v = _version_efectiva(prod)   # se origina sobre la versión VIGENTE hoy, no un borrador nuevo
    if v.estado != "PUBLICADO":
        raise HTTPException(409, "Sólo se puede originar sobre una línea PUBLICADA.")
    if not (float(v.monto_minimo) <= data.monto <= float(v.monto_maximo)):
        raise HTTPException(422, f"Monto fuera de rango ({float(v.monto_minimo):.0f}–{float(v.monto_maximo):.0f}).")
    if not (v.plazo_minimo <= data.plazo <= v.plazo_maximo):
        raise HTTPException(422, f"Plazo fuera de rango ({v.plazo_minimo}–{v.plazo_maximo}).")

    # Disponibilidad / segmentación (Fase E): valida el perfil del solicitante contra el producto.
    # Canal efectivo (H-184): originar desde el backoffice SIN canal explícito no debe saltear la
    # restricción de canal del producto — antes, `canal` vacío hacía que `_elegibilidad` no evaluara el
    # canal y un producto "solo WEB" quedaba originable como venta de sucursal. Se hereda el canal de la
    # solicitud web cuando la originación viene de una (procesar una solicitud del portal es legítimo);
    # si no hay solicitud, se asume SUCURSAL (contexto backoffice).
    canal_ef = data.canal or (sol_pp.canal if sol_pp else None) or canal_backoffice(db)
    elig = _elegibilidad(_disponibilidad(v), _ctx(data.segmento, canal_ef, data.edad, data.antiguedad_meses))
    if not elig["elegible"]:
        raise HTTPException(422, "No cumple la disponibilidad de la línea: " + " ".join(elig["motivos"]))

    calc_map = _calc_codigo_por_version(db)
    sistema = calc_map.get(v.calculador_version_id, "FRANCES")
    cargo = _cargo(v, "OTORGAMIENTO")
    hoy = date.today()

    # Tasa: efectiva del producto (helper único _tna_base: fija o índice+margen si VARIABLE),
    # o negociada dentro de la banda si el producto lo permite.
    tna_row = next((t for t in v.tasas if t.codigo == "TNA"), None)
    tna = _tna_base(db, v)
    if data.tasa is not None:
        if not (tna_row and tna_row.negociable and tna_row.modalidad == "FIJA"):
            raise HTTPException(422, "La tasa de esta línea no es negociable.")
        tmin, tmax = float(tna_row.tasa_minima), float(tna_row.tasa_maxima)
        if not (tmin <= data.tasa <= tmax):
            raise HTTPException(422, f"Tasa fuera de la banda negociable ({tmin:.2f}%–{tmax:.2f}%).")
        tna = data.tasa

    # Relationship pricing (Fase G): bonificación de TNA por la relación integral del cliente.
    # La banda de negociación es un PISO DURO: el descuento por relación no la puede perforar.
    if data.relacion and data.relacion.upper() not in RELACION_PRICING:
        raise HTTPException(422, f"Relación inválida: {data.relacion}. Válidas: {', '.join(RELACION_PRICING)}.")
    piso = float(tna_row.tasa_minima) if (tna_row and tna_row.negociable) else 0.0
    bonus = _bonus_relacion(data.relacion)
    tna = max(piso, 0.0, tna + bonus)

    feriados_eng = _feriados_engine(db)
    filas = cronograma(sistema, data.monto, data.plazo, tna, cargo, hoy, **_params_cronograma(v, feriados_eng, decimales_calculo(db)))

    es_var = bool(tna_row and tna_row.modalidad == "VARIABLE")
    snapshot = {"producto": prod.nombre, "codigo": prod.codigo, "version": v.numero_version,
                "sistema": sistema, "tna": tna, "cargo_otorgamiento": cargo,
                "base_dias": v.base_dias, "moneda": "ARS",
                "modalidad": tna_row.modalidad if tna_row else "FIJA",
                "indice": tna_row.indice_referencia if es_var else None,
                "margen": float(tna_row.margen) if es_var else None,
                "relacion": (data.relacion or "ESTANDAR").upper(), "bonus_relacion": bonus,
                "piso_relacion": piso,
                # La mora sólo aplica si el componente OVERDUE está activo en la versión.
                "mora_tna": (_tasa(v, "MORA") if _overdue_cfg(v) else 0.0),
                "dias_gracia_mora": _overdue_cfg(v).get("diasGracia", 0),
                # Params e importes pristinos, para regenerar el tramo restante ante un prepago.
                "frecuencia": v.frecuencia_pago or "MENSUAL",
                "impuestos": _params_cronograma(v).get("impuestos") or [],
                "cronograma_pristino": [{
                    "numero_cuota": f["numero_cuota"], "capital": float(f["capital"]),
                    "interes": float(f["interes"]), "cargos": float(f["cargos"]),
                    "impuestos": float(f["impuestos"]), "total": float(f["total"]),
                    "saldo_inicial": float(f["saldo_inicial"]), "saldo_final": float(f["saldo_final"]),
                } for f in filas],
                "contabilidad": _contab_cfg(v),
                "liquidacion": _liquidacion(data.monto, cargo, _params_cronograma(v))}
    # H-135: originar DESDE UNA SOLICITUD nunca desembolsa en el acto — el contrato queda A_LIQUIDAR y el
    # desembolso pasa por la liquidación por lote (circuito originación → lote diario → desembolso). La
    # originación directa (sin solicitud, p. ej. servicing/tests) mantiene el flag `desembolsar`.
    desde_solicitud = (sol_pp is not None) or (data.solicitud_id is not None)
    desembolsar_efectivo = data.desembolsar and not desde_solicitud
    def _mk_contrato(numero: str) -> m.PPContrato:
        c = m.PPContrato(
            producto_id=prod.id, producto_version_numero=v.numero_version,
            numero_contrato=numero, cliente_nombre=data.cliente_nombre.strip() or "Cliente",
            sistema=sistema, monto_original=Decimal(str(data.monto)), saldo_capital=Decimal(str(data.monto)),
            plazo=data.plazo, tasa_contratada=Decimal(str(tna)), fecha_valor=hoy,
            fecha_vencimiento=filas[-1]["fecha_vencimiento"],
            estado="ACTIVO" if desembolsar_efectivo else "A_LIQUIDAR",
            snapshot_producto=snapshot, datos_adicionales=data.datos_adicionales or {},
            solicitud_origen=data.solicitud_id, creado_por=user.username)
        db.add(c)
        return c
    # Número de contrato único aun con originaciones simultáneas (reintenta ante colisión).
    c = crear_con_numero_unico(db, lambda: _proximo_numero_contrato(db, hoy.year), _mk_contrato)
    for f in filas:
        db.add(m.PPCuotaContrato(contrato_id=c.id, **f))
    if sol_pp is not None:                        # solicitud nueva → queda ORIGINADA y ligada al contrato
        sol_pp.estado = "ORIGINADA"; sol_pp.contrato_id = c.id
    if desembolsar_efectivo:
        _desembolsar(db, c, user)   # asiento de otorgamiento + actividad de desembolso
    db.commit()
    return _serial_contrato(c, db)


def _desembolsar(db: Session, c: m.PPContrato, user) -> None:
    """Registra el desembolso: asiento contable de otorgamiento + actividad DISBURSEMENT."""
    asiento = cont.asiento_pp_otorgamiento(db, c)
    db.add(m.PPActividad(contrato_id=c.id, tipo="DISBURSEMENT", fecha=c.fecha_valor,
                         importe=c.monto_original, detalle="Desembolso inicial",
                         dato={"asiento_id": asiento.id}, creado_por=user.username))
    c.estado = "ACTIVO"
    db.flush()
    _recompute(c)   # marca cuotas sin importe (p. ej. bullet) como saldadas desde el arranque


def _gate_workflow(db: Session, objeto: str, c: m.PPContrato, datos: dict, user) -> dict | None:
    """Si la regla del objeto está activa, la operación no ejecuta: crea (o reusa) un pendiente de
    aprobación y devuelve el aviso. Si está inactiva, devuelve None (ejecutar directo)."""
    from app.services import workflow as wf
    r = wf.regla(db, objeto)
    if r is None or not r.activo:
        return None
    pend = db.query(m.PPWorkflowPendiente).filter_by(objeto=objeto, contrato_id=c.id, estado="PENDIENTE").first()
    if pend is None:
        pend = m.PPWorkflowPendiente(objeto=objeto, contrato_id=c.id, datos=datos, solicitado_por=user.username)
        db.add(pend); db.commit(); db.refresh(pend)
    return {"pendiente": True, "objeto": objeto, "pendienteId": pend.id, "contrato": c.numero_contrato,
            "mensaje": f"La operación quedó pendiente de aprobación (workflow {objeto})."}


def ejecutar_pendiente(db: Session, pend: m.PPWorkflowPendiente, user) -> dict:
    """Ejecuta la operación real de un pendiente ya aprobado (lo llama el flujo de aprobaciones)."""
    c = db.get(m.PPContrato, pend.contrato_id)
    if not c:
        raise HTTPException(404, "Contrato no encontrado")
    if pend.objeto == "DESEMBOLSO":
        if c.estado != "A_LIQUIDAR":
            raise HTTPException(409, f"El contrato está {c.estado}: no está pendiente de desembolso.")
        _desembolsar(db, c, user); db.commit()
        return _serial_contrato(c, db)
    if pend.objeto == "REFINANCIACION":
        data = RefinanciarIn(tasa=pend.datos.get("tasa", 0), plazo=int(pend.datos.get("plazo", 0)))
        return _refinanciar_impl(db, c.id, data, user, saltar_gate=True)
    raise HTTPException(422, f"Objeto de pendiente desconocido: {pend.objeto}")


@router.post("/{contrato_id}/desembolsar")
def desembolsar(contrato_id: str, db: Session = Depends(get_db),
                user: models.Usuario = Depends(get_current_user),
                idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Paso final de la originación: liquida y desembolsa un contrato A_LIQUIDAR.
    Si el workflow DESEMBOLSO está activo, queda pendiente de aprobación en vez de ejecutar."""
    def _do():   # idempotente: un reintento no liquida dos veces (H-108)
        c = db.get(m.PPContrato, contrato_id)
        if not c:
            raise HTTPException(404, "Contrato no encontrado")
        if c.estado != "A_LIQUIDAR":
            raise HTTPException(409, f"El contrato está {c.estado}: no está pendiente de desembolso.")
        gate = _gate_workflow(db, "DESEMBOLSO", c, {}, user)
        if gate is not None:
            return gate
        _desembolsar(db, c, user)
        db.commit()
        return _serial_contrato(c, db)
    return con_idempotencia(db, idempotency_key, "POST /api/contratos/{id}/desembolsar", _do, usuario=user.username)


class RefinanciarIn(BaseModel):
    tasa: float          # nueva TNA
    plazo: int           # nuevo plazo (cuotas)


@router.post("/{contrato_id}/refinanciar")
def refinanciar(contrato_id: str, data: RefinanciarIn, db: Session = Depends(get_db),
                user: models.Usuario = Depends(get_current_user),
                idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Refinancia el saldo con nueva tasa y plazo: cierra el contrato actual (REFINANCIADO) y crea
    uno nuevo sobre el saldo de capital (como un préstamo que cancela al anterior)."""
    # Idempotencia: un reintento con la misma clave no crea dos refinanciaciones.
    return con_idempotencia(db, idempotency_key, f"POST /api/contratos/{contrato_id}/refinanciar",
                            lambda: _refinanciar_impl(db, contrato_id, data, user), user.username)


def _refinanciar_impl(db: Session, contrato_id: str, data: RefinanciarIn, user, saltar_gate: bool = False) -> dict:
    c = db.get(m.PPContrato, contrato_id)
    if not c:
        raise HTTPException(404, "Contrato no encontrado")
    if c.estado != "ACTIVO":
        raise HTTPException(409, f"El contrato está {c.estado}: no se puede refinanciar.")
    saldo = c.saldo_capital or Decimal(0)
    if saldo <= 0:
        raise HTTPException(422, "El contrato no tiene saldo para refinanciar.")
    if data.plazo <= 0 or data.tasa < 0:
        raise HTTPException(422, "Tasa/plazo inválidos.")
    if not saltar_gate:                          # gate de workflow (si REFINANCIACION está activo)
        gate = _gate_workflow(db, "REFINANCIACION", c, {"tasa": data.tasa, "plazo": data.plazo}, user)
        if gate is not None:
            return gate
    snap = dict(c.snapshot_producto or {})
    hoy = date.today()
    filas = cronograma(snap.get("sistema", "FRANCES"), float(saldo), data.plazo, data.tasa,
                       cargo_pct=0.0, fecha_valor=hoy, frecuencia=snap.get("frecuencia", "MENSUAL"),
                       impuestos=snap.get("impuestos") or [], feriados=_feriados_engine(db))
    snap_new = {**snap, "tna": data.tasa, "refinancia_de": c.numero_contrato,
                "cronograma_pristino": [{
                    "numero_cuota": f["numero_cuota"], "capital": float(f["capital"]),
                    "interes": float(f["interes"]), "cargos": float(f["cargos"]),
                    "impuestos": float(f["impuestos"]), "total": float(f["total"]),
                    "saldo_inicial": float(f["saldo_inicial"]), "saldo_final": float(f["saldo_final"]),
                } for f in filas]}

    def _mk_nuevo(numero: str) -> m.PPContrato:
        nc = m.PPContrato(
            producto_id=c.producto_id, producto_version_numero=c.producto_version_numero,
            numero_contrato=numero, cliente_nombre=c.cliente_nombre,
            sistema=c.sistema, monto_original=saldo, saldo_capital=saldo, plazo=data.plazo,
            tasa_contratada=Decimal(str(data.tasa)), fecha_valor=hoy, fecha_vencimiento=filas[-1]["fecha_vencimiento"],
            estado="ACTIVO", snapshot_producto=snap_new,
            datos_adicionales={**(c.datos_adicionales or {}), "refinancia_de": c.numero_contrato},
            solicitud_origen=c.solicitud_origen, creado_por=user.username)
        db.add(nc)
        return nc
    nuevo = crear_con_numero_unico(db, lambda: _proximo_numero_contrato(db, hoy.year), _mk_nuevo)
    for f in filas:
        db.add(m.PPCuotaContrato(contrato_id=nuevo.id, **f))
    db.add(m.PPActividad(contrato_id=nuevo.id, tipo="DISBURSEMENT", fecha=hoy, importe=saldo,
                         detalle=f"Refinanciación de {c.numero_contrato}", creado_por=user.username))
    # Cierra el contrato original (saldado por la refinanciación).
    c.estado = "REFINANCIADO"
    c.datos_adicionales = {**(c.datos_adicionales or {}), "refinanciado_en": nuevo.numero_contrato}
    db.add(m.PPActividad(contrato_id=c.id, tipo="RENEGOTIATION", fecha=hoy, importe=saldo,
                         detalle=f"Refinanciado → {nuevo.numero_contrato} (TNA {data.tasa}% / {data.plazo} cuotas)",
                         creado_por=user.username))
    db.commit()
    return {"anterior": _serial_contrato(c, db), "nuevo": _serial_contrato(nuevo, db)}


@router.post("/{contrato_id}/devengar")
def devengar(contrato_id: str, db: Session = Depends(get_db),
             user: models.Usuario = Depends(get_current_user),
             idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Devenga el interés de la próxima cuota pendiente aún no devengada (asiento de devengo)."""
    def _do():   # idempotente: un reintento no genera dos asientos de devengo (H-108)
        c = db.get(m.PPContrato, contrato_id)
        if not c:
            raise HTTPException(404, "Contrato no encontrado")
        if c.estado != "ACTIVO":
            raise HTTPException(409, f"El contrato está {c.estado}: no admite devengamiento.")
        pend = [q for q in sorted(c.cuotas, key=lambda x: x.numero_cuota)
                if q.estado == "PENDIENTE" and not q.devengada]
        if not pend:
            raise HTTPException(409, "No hay cuotas pendientes por devengar.")
        q = pend[0]
        q.devengada = True
        asiento = cont.asiento_pp_devengo(db, c, q.interes, date.today(),
                                          f"Devengamiento interés cuota {q.numero_cuota} — contrato {c.numero_contrato}")
        db.add(m.PPActividad(contrato_id=c.id, tipo="ACCRUAL", fecha=date.today(), importe=q.interes,
                             detalle=f"Devengamiento interés cuota {q.numero_cuota}",
                             dato={"asiento_id": asiento.id, "cuota": q.numero_cuota}, creado_por=user.username))
        db.commit()
        return _serial_contrato(c, db)
    return con_idempotencia(db, idempotency_key, "POST /api/contratos/{id}/devengar", _do, usuario=user.username)


def _aplicar_prepago(c: m.PPContrato, cuotas, importe: Decimal, modo: str, tna: float) -> None:
    """Regenera las cuotas PENDIENTES tras un prepago de capital, preservando sus fechas.

    Reutiliza el motor `cronograma` (única fuente de verdad) para re-amortizar el nuevo saldo,
    sin re-cobrar el otorgamiento (cargo_pct=0) pero manteniendo los impuestos (IVA sobre interés).
    - BAJA_CUOTA: mismo número de cuotas pendientes, cuota menor.
    - BAJA_PLAZO: misma cuota (la francesa original), menos cuotas; las sobrantes quedan saldadas.
    """
    snap = c.snapshot_producto or {}
    pend = [q for q in cuotas if q.estado == "PENDIENTE"]
    if not pend or importe <= 0:
        return
    saldo_pend = sum((q.capital for q in pend), Decimal(0))
    nuevo = saldo_pend - importe
    if nuevo <= 0:   # el prepago cubre todo el capital restante → cuotas saldadas
        for q in pend:
            q.estado = "PAGADA"; q.pagado = q.total
        return
    sistema = snap.get("sistema", "FRANCES")
    frecuencia = snap.get("frecuencia", "MENSUAL")
    impuestos = snap.get("impuestos") or []
    k = len(pend)
    if str(modo).upper() == "BAJA_PLAZO":
        per = 3 if str(frecuencia).upper() == "TRIMESTRAL" else 1
        i = tna / 100 * per / 12
        cuota_orig = float(pend[0].capital) + float(pend[0].interes)   # cuota francesa original
        # períodos para amortizar `nuevo` con la cuota original (francés)
        import math
        if i > 0 and cuota_orig > float(nuevo) * i:
            m = math.ceil(math.log(cuota_orig / (cuota_orig - float(nuevo) * i)) / math.log(1 + i))
        else:
            m = k
        m = max(1, min(k, m))
    else:
        m = k   # BAJA_CUOTA: mismo número de cuotas
    filas = cronograma(sistema, float(nuevo), m, tna, cargo_pct=0.0,
                       frecuencia=frecuencia, impuestos=impuestos)
    for idx, q in enumerate(pend):
        if idx < m:
            f = filas[idx]
            q.capital = f["capital"]; q.interes = f["interes"]; q.cargos = f["cargos"]
            q.impuestos = f["impuestos"]; q.total = f["total"]
            q.saldo_inicial = f["saldo_inicial"]; q.saldo_final = f["saldo_final"]
            # Se PRESERVA el abono ya acumulado (un pago parcial previo no se pierde al regenerar).
            q.estado = "PAGADA" if (q.pagado or Decimal(0)) >= q.total else "PENDIENTE"
        else:   # cuotas sobrantes (BAJA_PLAZO): saldadas por el prepago, sin importe
            q.capital = Decimal(0); q.interes = Decimal(0); q.cargos = Decimal(0)
            q.impuestos = Decimal(0); q.total = Decimal(0); q.saldo_final = Decimal(0)
            q.estado = "PAGADA"; q.pagado = Decimal(0)


def _aplicar_holiday(c: m.PPContrato, cuotas, n: int, tna: float) -> None:
    """Diferimiento (payment holiday): saltea las próximas `n` cuotas capitalizando su interés.

    El interés de los `n` períodos diferidos se capitaliza al saldo (compuesto) y el tramo restante
    se re-amortiza sobre el nuevo saldo. Las `n` cuotas diferidas quedan en $0 (sin pago).
    """
    snap = c.snapshot_producto or {}
    pend = [q for q in cuotas if q.estado == "PENDIENTE"]
    if n <= 0 or n >= len(pend):
        return
    per = 3 if str(snap.get("frecuencia", "MENSUAL")).upper() == "TRIMESTRAL" else 1
    i = tna / 100 * per / 12
    saldo = float(sum((q.capital for q in pend), Decimal(0)))
    nuevo = saldo * ((1 + i) ** n)                     # interés capitalizado en los n períodos
    for q in pend[:n]:                                  # cuotas diferidas: sin pago
        q.capital = Decimal(0); q.interes = Decimal(0); q.cargos = Decimal(0)
        q.impuestos = Decimal(0); q.total = Decimal(0); q.saldo_final = Decimal(str(round(nuevo, 2)))
    filas = cronograma(snap.get("sistema", "FRANCES"), nuevo, len(pend) - n, tna, cargo_pct=0.0,
                       frecuencia=snap.get("frecuencia", "MENSUAL"), impuestos=snap.get("impuestos") or [])
    for idx, q in enumerate(pend[n:]):
        f = filas[idx]
        q.capital = f["capital"]; q.interes = f["interes"]; q.cargos = f["cargos"]
        q.impuestos = f["impuestos"]; q.total = f["total"]
        q.saldo_inicial = f["saldo_inicial"]; q.saldo_final = f["saldo_final"]


def _recompute(c: m.PPContrato) -> None:
    """Reconstruye el estado del contrato reproduciendo sus actividades no reversadas.

    Event-sourcing: parte del cronograma pristino (los importes de cada cuota no cambian
    con los pagos, sólo su estado) y aplica en orden de fecha valor los efectos. Así el
    backdating reordena y la reversa es simplemente marcar+recomputar.
    """
    cuotas = sorted(c.cuotas, key=lambda x: x.numero_cuota)
    # Reset a los importes PRISTINOS del snapshot (así regenerar por prepago es idempotente:
    # cada recompute parte del cronograma original y vuelve a aplicar los prepagos).
    prist = {p["numero_cuota"]: p for p in (c.snapshot_producto or {}).get("cronograma_pristino", [])}
    for q in cuotas:
        p = prist.get(q.numero_cuota)
        if p:
            q.capital = Decimal(str(p["capital"])); q.interes = Decimal(str(p["interes"]))
            q.cargos = Decimal(str(p["cargos"])); q.impuestos = Decimal(str(p["impuestos"]))
            q.total = Decimal(str(p["total"])); q.saldo_inicial = Decimal(str(p["saldo_inicial"]))
            q.saldo_final = Decimal(str(p["saldo_final"]))
        # Una cuota sin importe (ej. períodos sin pago de un bullet) se considera saldada.
        q.estado = "PAGADA" if (q.total or Decimal(0)) <= 0 else "PENDIENTE"
        q.pagado = Decimal(0)
    c.saldo_capital = c.monto_original
    c.estado = "ACTIVO"
    tasa = Decimal(str((c.snapshot_producto or {}).get("tna", c.tasa_contratada)))
    acts = [a for a in c.actividades if a.estado != "REVERSADA" and a.tipo != "REVERSAL"]
    for a in sorted(acts, key=lambda x: (x.fecha, x.creado_en)):
        if a.tipo == "PAYMENT":
            # Abono neto de mora (el punitorio no amortiza cuota). Se aplica a las cuotas
            # pendientes en orden, acumulando en `pagado`; una cuota se marca PAGADA sólo al
            # completar su total. Soporta pago total (llena una cuota) y parcial (acumula).
            d = a.dato or {}
            mora = Decimal(str(d.get("interes_punitorio", 0))) + Decimal(str(d.get("iva_punitorio", 0)))
            abono = (a.importe or Decimal(0)) - mora
            for q in cuotas:
                if abono <= 0:
                    break
                if q.estado == "PAGADA":
                    continue
                falta = (q.total or Decimal(0)) - (q.pagado or Decimal(0))
                aplica = min(abono, falta)
                q.pagado = (q.pagado or Decimal(0)) + aplica
                abono -= aplica
                if q.pagado >= q.total:
                    q.estado = "PAGADA"
                    c.saldo_capital = max(Decimal(0), (c.saldo_capital or Decimal(0)) - q.capital)
        elif a.tipo == "PAYOFF":
            for q in cuotas:
                if q.estado == "PENDIENTE":
                    q.estado = "PAGADA"; q.pagado = q.total
            c.saldo_capital = Decimal(0)
        elif a.tipo == "REPRICING" and a.dato:  # Fase G: repricing periódico de tasa variable
            tasa = Decimal(str(a.dato.get("tasa_nueva", tasa)))
        elif a.tipo == "PARTIAL_PREPAYMENT" and a.dato:
            # Prepago de capital: aplica el importe al saldo y REGENERA el tramo pendiente
            # (baja cuota = mismo plazo / baja plazo = misma cuota), preservando las fechas.
            _aplicar_prepago(c, cuotas, Decimal(str(a.dato.get("importe", 0))),
                             a.dato.get("modo", "BAJA_PLAZO"), float(tasa))
            c.saldo_capital = sum((q.capital for q in cuotas if q.estado == "PENDIENTE"), Decimal(0))
        elif a.tipo == "PAYMENT_HOLIDAY" and a.dato:
            _aplicar_holiday(c, cuotas, int(a.dato.get("cuotas", 0)), float(tasa))
            c.saldo_capital = sum((q.capital for q in cuotas if q.estado == "PENDIENTE"), Decimal(0))
        # RATE_CHANGE / RENEGOTIATION: sin efecto en cuotas (se registran / la refi genera un contrato nuevo)
    c.tasa_contratada = tasa
    if any(a.tipo == "RENEGOTIATION" and a.estado != "REVERSADA" for a in c.actividades):
        c.estado = "REFINANCIADO"
    elif cuotas and all(q.estado == "PAGADA" for q in cuotas):
        c.estado = "CERRADO"
        c.saldo_capital = Decimal(0)   # préstamo saldado: sin residuo de redondeo


def _parse_fecha(c: m.PPContrato, s: str | None) -> date:
    hoy = date.today()
    if not s:
        return hoy
    try:
        f = date.fromisoformat(s)
    except ValueError:
        raise HTTPException(422, f"Fecha inválida: {s} (formato ISO AAAA-MM-DD).")
    if f > hoy:
        raise HTTPException(422, "La fecha valor no puede ser futura.")
    if f < c.fecha_valor:
        raise HTTPException(422, f"La fecha valor no puede ser anterior al desembolso ({c.fecha_valor}).")
    return f


@router.post("/{contrato_id}/actividad")
def actividad(contrato_id: str, data: ActividadIn, request: Request, db: Session = Depends(get_db),
              user: models.Usuario = Depends(get_current_user),
              idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    # Idempotencia: un reintento (doble clic en "Pagar"/"Cobrar") no registra el movimiento dos veces.
    origen_ip = audit.ip_de(request)
    prev = db.get(m.PPContrato, contrato_id)
    antes = {"estado": prev.estado, "saldo_capital": _fmt(prev.saldo_capital)} if prev else None
    resumen = {"tipo": data.tipo, "importe": data.importe, "fecha": data.fecha, "medio_pago": data.medio_pago}
    try:
        res = con_idempotencia(db, idempotency_key, f"POST /api/contratos/{contrato_id}/actividad",
                               lambda: _actividad_impl(db, contrato_id, data, user), user.username)
    except HTTPException as e:
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=origen_ip,
                               entidad="Contrato", entidad_id=contrato_id, operacion="PAGAR",
                               resultado="RECHAZADO", antes=antes, despues=resumen,
                               detalle=f"{data.tipo} rechazado: {e.detail}")
        raise
    audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=origen_ip,
                           entidad="Contrato", entidad_id=contrato_id, operacion="PAGAR", resultado="OK",
                           antes=antes,
                           despues={**resumen, "estado": (res or {}).get("estado"),
                                    "saldo_capital": (res or {}).get("saldo_capital")},
                           detalle=f"{data.tipo} registrado en contrato {(res or {}).get('numero_contrato', contrato_id)}")
    return res


def _actividad_impl(db: Session, contrato_id: str, data: ActividadIn, user) -> dict:
    c = db.get(m.PPContrato, contrato_id)
    if not c:
        raise HTTPException(404, "Contrato no encontrado")
    if c.estado == "A_LIQUIDAR":
        raise HTTPException(409, "El contrato aún no fue desembolsado.")
    if c.estado in ("CERRADO", "CANCELADO", "CASTIGADO", "REFINANCIADO"):
        raise HTTPException(409, f"El contrato está {c.estado}: no admite actividades.")
    if data.tipo not in ("PAYMENT", "PAYOFF", "RATE_CHANGE", "PARTIAL_PREPAYMENT", "PAYMENT_HOLIDAY", "RENEGOTIATION", "REPRICING"):
        raise HTTPException(422, f"Tipo de actividad no soportado: {data.tipo}")
    fecha = _parse_fecha(c, data.fecha)
    detalle = data.detalle
    dato = None

    # Adelanto de N cuotas: registra N pagos completos (cada uno con su mora y asiento).
    if data.tipo == "PAYMENT" and int(data.cuotas or 1) > 1:
        pend = [q for q in sorted(c.cuotas, key=lambda x: x.numero_cuota) if q.estado == "PENDIENTE" and (q.total or Decimal(0)) > 0]
        if not pend:
            raise HTTPException(409, "No hay cuotas pendientes.")
        n = min(int(data.cuotas), len(pend))
        medio = {"medio_pago": data.medio_pago.upper()} if data.medio_pago else {}
        for q in pend[:n]:
            ip, iv, dias = _mora_de_cuota(c, q, fecha)
            imp = (q.total or Decimal(0)) - (q.pagado or Decimal(0)) + ip + iv
            d = {"mora_dias": dias, "interes_punitorio": float(ip), "iva_punitorio": float(iv)} if (ip + iv) > 0 else {}
            act = m.PPActividad(contrato_id=c.id, tipo="PAYMENT", fecha=fecha, importe=imp,
                                dato={**d, **medio} or None,
                                detalle=f"Adelanto: pago cuota {q.numero_cuota}", creado_por=user.username)
            db.add(act); db.flush()
            asi = cont.asiento_pp_pago(db, c, q, fecha,
                                       f"Pago cuota {q.numero_cuota} (adelanto) — contrato {c.numero_contrato}",
                                       int_punitorio=ip, iva_punitorio=iv)
            act.dato = {**(act.dato or {}), "asiento_id": asi.id}
        _recompute(c); db.commit()
        return _serial_contrato(c, db)

    cuota_pago = None
    parcial = False
    if data.tipo == "PAYMENT":
        pend = [q for q in sorted(c.cuotas, key=lambda x: x.numero_cuota) if q.estado == "PENDIENTE" and (q.total or Decimal(0)) > 0]
        if not pend:
            raise HTTPException(409, "No hay cuotas pendientes.")
        cuota_pago = pend[0]
        falta = (cuota_pago.total or Decimal(0)) - (cuota_pago.pagado or Decimal(0))   # saldo de la cuota
        pedido = Decimal(str(data.importe or 0))
        int_pun, iva_pun, dias_mora = _mora_de_cuota(c, cuota_pago, fecha)
        mora_total = int_pun + iva_pun
        if 0 < pedido < falta:
            # PAGO PARCIAL: abona una parte de la cuota (no la completa). Sin mora en el parcial.
            parcial = True
            importe = pedido
            int_pun = iva_pun = Decimal(0)
            detalle = detalle or f"Pago parcial cuota {cuota_pago.numero_cuota} (${pedido} de ${falta})"
        else:
            # PAGO TOTAL de lo que falta de la cuota (+ mora si está vencida).
            importe = falta + mora_total
            detalle = detalle or f"Pago de cuota {cuota_pago.numero_cuota}" + (
                f" + mora {dias_mora}d (${mora_total})" if mora_total > 0 else "")
            if mora_total > 0:
                dato = {"mora_dias": dias_mora, "interes_punitorio": float(int_pun),
                        "iva_punitorio": float(iva_pun)}
    elif data.tipo == "PAYOFF":
        importe = c.saldo_capital or Decimal(0)
        detalle = detalle or "Cancelación anticipada total (payoff)"
    elif data.tipo == "PARTIAL_PREPAYMENT":
        importe = Decimal(str(data.importe or 0))
        saldo = c.saldo_capital or Decimal(0)
        if importe <= 0:
            raise HTTPException(422, "El prepago requiere un importe mayor a cero.")
        if importe > saldo:
            raise HTTPException(422, f"El prepago (${importe}) supera el saldo de capital (${saldo}). Usá Cancelación total.")
        modo = (data.modo or "BAJA_PLAZO").upper()
        if modo not in ("BAJA_PLAZO", "BAJA_CUOTA"):
            raise HTTPException(422, "Modo inválido: BAJA_PLAZO o BAJA_CUOTA.")
        dato = {"importe": float(importe), "modo": modo}
        detalle = detalle or f"Prepago de capital ${importe} ({'baja plazo' if modo == 'BAJA_PLAZO' else 'baja cuota'})"
    elif data.tipo == "PAYMENT_HOLIDAY":
        n = int(data.importe or 0)   # cantidad de cuotas a diferir
        pend = [q for q in c.cuotas if q.estado == "PENDIENTE"]
        if not (0 < n < len(pend)):
            raise HTTPException(422, f"Cuotas a diferir inválidas: entre 1 y {len(pend) - 1}.")
        importe = Decimal(0)
        dato = {"cuotas": n}
        detalle = detalle or f"Diferimiento de {n} cuota(s) — el interés se capitaliza"
    elif data.tipo == "REPRICING":
        # Regla periódica (Fase G): recalcula la TNA de una línea de tasa variable desde el índice.
        snap = c.snapshot_producto or {}
        if not snap.get("indice"):
            raise HTTPException(422, "Sólo las líneas de tasa variable admiten repricing.")
        val = config.indice_valor(snap["indice"]) or 0.0
        # El piso de la banda también aplica al repricing: el índice+margen+bonus no lo perfora.
        nueva = max(float(snap.get("piso_relacion") or 0.0), 0.0,
                    val + float(snap.get("margen") or 0.0) + float(snap.get("bonus_relacion") or 0.0))
        dato = {"tasa_anterior": float(c.tasa_contratada), "tasa_nueva": nueva, "indice": snap["indice"], "indice_valor": val}
        importe = Decimal(0)
        detalle = detalle or f"Repricing: TNA {float(c.tasa_contratada):.2f}%→{nueva:.2f}% ({snap['indice']} {val:.2f}% + margen {snap.get('margen')}%)"
    else:
        importe = Decimal(str(data.importe))
        detalle = detalle or f"Actividad {data.tipo} registrada"

    if data.medio_pago:
        dato = {**(dato or {}), "medio_pago": data.medio_pago.upper()}
    act = m.PPActividad(contrato_id=c.id, tipo=data.tipo, fecha=fecha, dato=dato,
                        importe=Decimal(str(importe)), detalle=detalle, creado_por=user.username)
    db.add(act); db.flush()
    # Asiento contable de la cobranza (integración con Contabilidad → Libro Diario)
    asiento = None
    if data.tipo == "PAYMENT" and cuota_pago is not None:
        asiento = cont.asiento_pp_pago(db, c, cuota_pago, fecha,
                                       (f"Pago parcial cuota {cuota_pago.numero_cuota}" if parcial else f"Pago cuota {cuota_pago.numero_cuota}") + f" — contrato {c.numero_contrato}",
                                       int_punitorio=int_pun, iva_punitorio=iva_pun,
                                       monto=Decimal(str(importe)) if parcial else None)
    elif data.tipo == "PAYOFF":
        asiento = cont.asiento_pp_payoff(db, c, importe, fecha,
                                         f"Cancelación total — contrato {c.numero_contrato}")
    elif data.tipo == "PARTIAL_PREPAYMENT":
        # Debe Caja / Haber capital, por el importe prepagado (baja el capital).
        asiento = cont.asiento_pp_payoff(db, c, importe, fecha,
                                         f"Prepago de capital — contrato {c.numero_contrato}")
    if asiento is not None:
        act.dato = {**(act.dato or {}), "asiento_id": asiento.id}
    _recompute(c)
    db.commit()
    return _serial_contrato(c, db)


@router.post("/{contrato_id}/actividad/{actividad_id}/reversar")
def reversar(contrato_id: str, actividad_id: str, db: Session = Depends(get_db),
             user: models.Usuario = Depends(get_current_user)):
    """Reversa una actividad: la marca REVERSADA, asienta una entrada REVERSAL y recomputa."""
    c = db.get(m.PPContrato, contrato_id)
    if not c:
        raise HTTPException(404, "Contrato no encontrado")
    a = db.get(m.PPActividad, actividad_id)
    if not a or a.contrato_id != c.id:
        raise HTTPException(404, "Actividad no encontrada")
    if a.tipo in ("DISBURSEMENT", "REVERSAL"):
        raise HTTPException(422, "No se puede reversar el desembolso ni una reversa.")
    if a.tipo == "RENEGOTIATION":
        # H-154: reversar la refinanciación reactivaría el contrato viejo (recompute → ACTIVO con el saldo
        # entero) mientras el nuevo sigue vivo con su propio desembolso → el mismo capital quedaría colocado
        # dos veces. No hay reversa segura genérica (el contrato nuevo puede ya tener pagos), así que se
        # bloquea: para deshacer una refinanciación hay que operar sobre el contrato nuevo.
        nuevo = (c.datos_adicionales or {}).get("refinanciado_en") or ""
        raise HTTPException(422, "No se puede reversar una refinanciación desde el contrato original"
                            + (f" (se refinanció en {nuevo})" if nuevo else "")
                            + ". Operá sobre el contrato nuevo para deshacerla.")
    if a.estado == "REVERSADA":
        raise HTTPException(409, "La actividad ya está reversada.")
    a.estado = "REVERSADA"
    # Contra-asiento si la actividad revertida había generado un asiento contable
    asiento_orig = db.get(models.Asiento, a.dato["asiento_id"]) if (a.dato and a.dato.get("asiento_id")) else None
    if asiento_orig is not None:
        cont.asiento_pp_reversa(db, asiento_orig, date.today())
    db.add(m.PPActividad(contrato_id=c.id, tipo="REVERSAL", fecha=date.today(),
                         importe=a.importe, reversa_de=a.id, creado_por=user.username,
                         detalle=f"Reversa de {a.tipo} del {a.fecha}"))
    try:
        db.flush()
    except IntegrityError:
        # Carrera: otro request ya reversó esta actividad (uq_pp_actividad_reversa_de). La DB es árbitro:
        # no se generan dos contra-asientos. El segundo reintento ve el 409.
        db.rollback()
        raise HTTPException(409, "La actividad ya está reversada.")
    _recompute(c)
    db.commit()
    return _serial_contrato(c, db)
