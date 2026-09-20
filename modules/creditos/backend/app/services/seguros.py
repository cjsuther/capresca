"""Servicios del módulo Seguros: pólizas y liquidación a la compañía.

El seguro de vida se cobra por cuota (columna `seguro` de la cuota/pago). La
liquidación de seguros agrega lo cobrado en un período para remitirlo a la
aseguradora (VFP: liqsegur / cajacreseg).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, func, case
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


def polizas_vigentes(db: Session, *, q: str | None = None, codigo: int | None = None,
                     solo_vigentes: bool = True, limit: int = 50, offset: int = 0) -> dict:
    """Pólizas de seguro de vida por agente (VFP: seguros.dbf), con resumen por
    tipo y búsqueda por CUIL, nº de agente o nº de póliza.

    'Vigente' = ESTADO 'A' y no dada de baja, igual que el legacy (207 mil
    pólizas, mayormente estado 'A')."""
    P = models.PolizaAgente
    base = select(P)
    if solo_vigentes:
        base = base.where(P.estado == "A", P.baja.is_(False))
    if codigo:
        base = base.where(P.codigo == codigo)
    if q:
        term = q.strip()
        if term.isdigit():
            base = base.where((P.cuil == term) | (P.no_agente == int(term)) |
                              (P.no_poliza == int(term)))
        else:
            base = base.where(P.cuil.like(f"{term}%"))

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    filas = db.scalars(base.order_by(P.no_agente, P.codigo).limit(limit).offset(offset)).all()

    # Resumen por tipo sobre el mismo filtro (sin paginar).
    res_q = select(P.codigo, func.count(), func.coalesce(func.sum(P.cantidad), 0))
    if solo_vigentes:
        res_q = res_q.where(P.estado == "A", P.baja.is_(False))
    if codigo:
        res_q = res_q.where(P.codigo == codigo)
    resumen = [
        {"codigo": c, "tipo": TIPOS_SEGURO.get(c, f"Tipo {c}"),
         "polizas": n, "cantidad": int(cant)}
        for c, n, cant in db.execute(res_q.group_by(P.codigo).order_by(P.codigo)).all()
    ]
    items = [
        {"id": p.id, "codigo": p.codigo, "tipo": TIPOS_SEGURO.get(p.codigo, f"Tipo {p.codigo}"),
         "no_poliza": p.no_poliza, "cuil": p.cuil, "no_agente": p.no_agente,
         "sexo": p.sexo, "cantidad": p.cantidad, "estado": p.estado,
         "fecha": p.fecha, "fecha_alta": p.fecha_alta}
        for p in filas
    ]
    return {"total": total, "limit": limit, "offset": offset,
            "resumen": resumen, "items": items}


def titulares(db: Session, *, q: str | None = None, tipo: str | None = None,
              limit: int = 25, offset: int = 0) -> dict:
    """Maestro de titulares del seguro de vida colectivo (VFP: titulares)."""
    T = models.TitularSeguro
    cols = (T.id, T.cuil, T.apellido_nombre, T.tipo_titular, T.organo, T.sexo,
            T.no_agente, T.fecha_nac, T.localidad, T.cantidad)
    base = select(*cols)
    if tipo:
        base = base.where(T.tipo_titular == tipo)
    if q:
        like = f"%{q.upper()}%"
        base = base.where(T.apellido_nombre.like(like) | T.cuil.like(like))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    # Los titulares sin nombre cargado (634 de 122.784 en el dato real) se muestran al
    # final para no ocultar los que sí tienen nombre en la primera página.
    rows = db.execute(base.order_by(case((T.apellido_nombre == "", 1), else_=0),
                                    T.apellido_nombre)
                      .limit(min(limit, 200)).offset(max(offset, 0))).all()
    items = [{"id": r.id, "cuil": r.cuil, "apellido_nombre": r.apellido_nombre,
              "tipo_titular": r.tipo_titular, "organo": r.organo, "sexo": r.sexo,
              "no_agente": r.no_agente, "fecha_nac": r.fecha_nac,
              "localidad": r.localidad, "cantidad": r.cantidad} for r in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


def resumen_seguro_adicional(db: Session, periodo: str | None = None) -> dict:
    """Totales del seguro del agente por concepto (VFP: infsegadicional).

    Cuenta agentes con y sin seguro de vida adicional (SEG_ADICIO)."""
    S = models.SeguroAgente
    base = select(S)
    if periodo:
        base = base.where(S.periodo == periodo)
    tot = base.with_only_columns(
        func.count(S.id),
        func.coalesce(func.sum(S.seg_obligatorio), 0),
        func.coalesce(func.sum(S.seg_sepelio), 0),
        func.coalesce(func.sum(S.seg_conyuge), 0),
        func.coalesce(func.sum(S.seg_adicional), 0),
    )
    n, oblig, sepe, cony, adic = db.execute(tot).one()
    con_adic = db.scalar(base.with_only_columns(func.count(S.id))
                         .where(S.seg_adicional > 0)) or 0
    return {"periodo": periodo or "(todos)", "agentes": n,
            "con_adicional": con_adic, "sin_adicional": n - con_adic,
            "total_obligatorio": Decimal(oblig), "total_sepelio": Decimal(sepe),
            "total_conyuge": Decimal(cony), "total_adicional": Decimal(adic)}


def agentes_seguro_adicional(db: Session, *, con_adicional: bool, periodo: str | None,
                             q: str | None, limit: int, offset: int) -> dict:
    """Lista paginada de agentes con/sin seguro adicional (VFP: infsegadicional /
    informeagentessinseguroadicional)."""
    S = models.SeguroAgente
    base = select(S)
    if periodo:
        base = base.where(S.periodo == periodo)
    base = base.where(S.seg_adicional > 0) if con_adicional else base.where(S.seg_adicional <= 0)
    if q:
        like = f"%{q.upper()}%"
        base = base.where(S.titular.like(like) | S.cuil.like(like))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(S.titular).limit(min(limit, 200)).offset(max(offset, 0))).all()
    items = [{"cuil": s.cuil, "titular": s.titular, "remuneracion": s.remuneracion,
              "seg_obligatorio": s.seg_obligatorio, "seg_sepelio": s.seg_sepelio,
              "seg_conyuge": s.seg_conyuge, "seg_adicional": s.seg_adicional}
             for s in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


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


def seguros_cobrados(db: Session, desde: date, hasta: date) -> dict:
    """Resumen de seguros cobrados en un período (VFP: frm730050000rptcobseg).

    Suma el componente de seguro cobrado (PagoCuota.seguro) de los recibos del
    período, con detalle por día.
    """
    from collections import defaultdict
    q = (
        select(models.Recibo.fecha_pago, func.coalesce(func.sum(models.PagoCuota.seguro), 0),
               func.count(func.distinct(models.Recibo.id)))
        .join(models.PagoCuota, models.PagoCuota.recibo_id == models.Recibo.id)
        .where(models.Recibo.fecha_pago >= desde, models.Recibo.fecha_pago <= hasta,
               models.Recibo.estado == "E")
        .group_by(models.Recibo.fecha_pago).order_by(models.Recibo.fecha_pago)
    )
    dias = []
    total = CERO
    for fecha, seguro, nrec in db.execute(q).all():
        dias.append({"fecha": fecha, "recibos": nrec, "seguro": Decimal(seguro)})
        total += Decimal(seguro)
    return {"desde": desde, "hasta": hasta, "total_seguro": total, "dias": dias}


def primas_devengadas(db: Session, desde: date, hasta: date) -> dict:
    """Primas de seguro devengadas en el período (VFP: frm715100000cons_primas).

    Devengado = seguro de cuotas cuyo vencimiento cae en el período.
    Cobrado = las de esas cuotas ya pagadas. Pendiente = devengado - cobrado.
    """
    base = select(func.coalesce(func.sum(models.Cuota.seguro), 0)).where(
        models.Cuota.fecha_vencimiento >= desde,
        models.Cuota.fecha_vencimiento <= hasta)
    devengado = Decimal(db.scalar(base) or 0)
    cobrado = Decimal(db.scalar(base.where(models.Cuota.estado == "P")) or 0)
    return {"desde": desde, "hasta": hasta, "devengado": devengado,
            "cobrado": cobrado, "pendiente": devengado - cobrado}


def pagos_seguros(db: Session, desde: date, hasta: date) -> dict:
    """Pagos de seguros emitidos (OP tipo SEGURO) en el período.

    Cubre 'Pagos de Seguros' (frm720150000pagosseguros) y las OP de regímenes.
    """
    ops = db.scalars(
        select(models.OrdenPago).where(
            models.OrdenPago.tipo == "SEGURO",
            models.OrdenPago.fecha >= desde, models.OrdenPago.fecha <= hasta)
        .order_by(models.OrdenPago.numero)).all()
    total = sum((o.importe for o in ops), CERO)
    items = [{"numero": o.numero, "fecha": o.fecha, "beneficiario": o.beneficiario,
              "concepto": o.concepto, "importe": o.importe, "estado": o.estado}
             for o in ops]
    return {"desde": desde, "hasta": hasta, "cantidad": len(ops),
            "total": total, "items": items}


def liquidacion(db: Session, desde: date, hasta: date,
                compania_id: int | None = None) -> list[dict]:
    """Seguro cobrado por período agrupado por compañía (monto a remitir)."""
    q = (
        select(
            models.CompaniaSeguros.id,
            models.CompaniaSeguros.nombre,
            func.count(func.distinct(models.Recibo.id)),
            func.coalesce(func.sum(models.PagoCuota.seguro), 0),
        )
        .join(models.Recibo, models.Recibo.id == models.PagoCuota.recibo_id)
        .join(models.Credito, models.Credito.id == models.Recibo.credito_id)
        .join(models.Poliza, models.Poliza.credito_id == models.Credito.id)
        .join(models.CompaniaSeguros,
              models.CompaniaSeguros.id == models.Poliza.compania_id)
        .where(models.Recibo.fecha_pago >= desde,
               models.Recibo.fecha_pago <= hasta,
               models.Recibo.estado == "E")
        .group_by(models.CompaniaSeguros.id, models.CompaniaSeguros.nombre)
    )
    if compania_id:
        q = q.where(models.CompaniaSeguros.id == compania_id)

    out = []
    for cid, nombre, nrec, total in db.execute(q).all():
        out.append({"compania_id": cid, "compania": nombre,
                    "cantidad_recibos": nrec, "total_seguro": Decimal(total)})
    return out
