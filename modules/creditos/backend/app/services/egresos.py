"""Servicios del módulo Tesorería / Egresos: órdenes de pago.

Cubre el desembolso de créditos, pagos a aseguradoras y a proveedores
(licitaciones/compras). VFP: agjsegresos (maeop, chequeras, pagos).
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


def reporte_ordenes(db: Session, desde: date | None = None,
                    hasta: date | None = None) -> dict:
    """Reporte de OP agrupado por tipo, con desglose por estado (VFP: rptoprb, rptop)."""
    O = models.OrdenPago
    q = select(O.tipo, O.estado, func.count(O.id),
               func.coalesce(func.sum(O.importe), 0)).group_by(O.tipo, O.estado)
    if desde:
        q = q.where(O.fecha >= desde)
    if hasta:
        q = q.where(O.fecha <= hasta)

    por_tipo: dict[str, dict] = {}
    tot = {"tipo": "TOTAL", "cantidad": 0, "pendiente": Decimal("0"),
           "girado": Decimal("0"), "anulado": Decimal("0"), "importe": Decimal("0")}
    for tipo, estado, n, imp in db.execute(q).all():
        imp = Decimal(imp)
        fila = por_tipo.setdefault(tipo or "(sin tipo)", {
            "tipo": tipo or "(sin tipo)", "cantidad": 0,
            "pendiente": Decimal("0"), "girado": Decimal("0"),
            "anulado": Decimal("0"), "importe": Decimal("0")})
        clave = _ESTADOS.get(estado, "pendiente")
        fila[clave] += imp
        fila["cantidad"] += n
        # El importe total del tipo excluye lo anulado.
        if estado != "A":
            fila["importe"] += imp
            tot["importe"] += imp
        tot[clave] += imp
        tot["cantidad"] += n
    filas = sorted(por_tipo.values(), key=lambda f: f["importe"], reverse=True)
    return {"por_tipo": filas, "total": tot}


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


def pagar_op(db: Session, op_id: int, *, banco: str, cheque_numero: str,
             fecha_pago: date | None = None) -> models.OrdenPago:
    op = db.get(models.OrdenPago, op_id)
    if not op:
        raise ReglaNegocioError("Orden de pago inexistente")
    if op.estado == "G":
        raise ReglaNegocioError("La orden de pago ya fue girada")
    if op.estado == "A":
        raise ReglaNegocioError("La orden de pago está anulada")
    op.estado = "G"
    op.banco = banco
    op.cheque_numero = cheque_numero
    op.medio_pago = "CHEQUE"
    op.fecha_pago = fecha_pago or date.today()
    db.commit()
    db.refresh(op)
    return op


def anular_op(db: Session, op_id: int) -> models.OrdenPago:
    op = db.get(models.OrdenPago, op_id)
    if not op:
        raise ReglaNegocioError("Orden de pago inexistente")
    if op.estado == "G":
        raise ReglaNegocioError("No se puede anular una OP ya girada")
    op.estado = "A"
    db.commit()
    db.refresh(op)
    return op


def crear_chequera(db: Session, *, banco: str, cuenta: str, desde: int,
                   hasta: int) -> models.Chequera:
    if hasta < desde:
        raise ReglaNegocioError("El rango de la chequera es inválido")
    ch = models.Chequera(banco=banco, cuenta=cuenta, numero_desde=desde,
                         numero_hasta=hasta, proximo=desde, activa=True)
    db.add(ch)
    db.commit()
    db.refresh(ch)
    return ch


def pagar_op_con_chequera(db: Session, op_id: int, chequera_id: int,
                          fecha_pago: date | None = None) -> models.OrdenPago:
    """Paga una OP tomando el próximo cheque de una chequera activa."""
    ch = db.get(models.Chequera, chequera_id)
    if not ch or not ch.activa:
        raise ReglaNegocioError("Chequera inexistente o inactiva")
    if ch.proximo > ch.numero_hasta:
        raise ReglaNegocioError("La chequera está agotada")
    op = pagar_op(db, op_id, banco=ch.banco, cheque_numero=str(ch.proximo),
                  fecha_pago=fecha_pago)
    ch.proximo += 1
    if ch.proximo > ch.numero_hasta:
        ch.activa = False
    db.commit()
    db.refresh(op)
    return op


def pagos_pendientes_incompletos(db: Session) -> dict:
    """Revisión: OP pendientes y OP incompletas (importe 0) (frm825xxx)."""
    pendientes = db.scalars(select(models.OrdenPago).where(
        models.OrdenPago.estado == "P").order_by(models.OrdenPago.fecha)).all()
    def r(o):
        return {"numero": o.numero, "fecha": o.fecha, "beneficiario": o.beneficiario,
                "concepto": o.concepto, "importe": o.importe, "tipo": o.tipo}
    return {
        "pendientes": [r(o) for o in pendientes],
        "incompletas": [r(o) for o in pendientes if o.importe <= 0],
        "total_pendiente": sum((o.importe for o in pendientes), Decimal("0")),
    }


def totales(db: Session) -> dict:
    def suma(estado):
        return db.scalar(select(func.coalesce(func.sum(models.OrdenPago.importe), 0))
                         .where(models.OrdenPago.estado == estado)) or Decimal("0")
    return {
        "pendiente": Decimal(suma("P")),
        "girado": Decimal(suma("G")),
    }


def consumir_cupo(db: Session, *, nop: int, importe: Decimal, fecha: date | None = None,
                  sistema: str | None = None) -> models.AutorizacionOP:
    """Consume el saldo de una autorización/cupo de OP al registrar un pago (VFP:
    frm820100000pagostesoreria). Validaciones EXACTAS del fuente:
      1. la OP (cupo) existe,
      2. está habilitada y no anulada/cancelada,
      3. no está vencida (`fvigencia > hoy`),
      4. el `sistema` coincide (si se indica),
      5. el saldo alcanza (`nsaldo >= importe`).
    Luego: importe_usado += importe, saldo = importe − usado (invariante verificado en
    el dato real, 34.845/35.040)."""
    importe = Decimal(importe)
    if importe <= 0:
        raise ReglaNegocioError("El importe a consumir debe ser positivo")
    cupo = db.scalars(select(models.AutorizacionOP).where(
        models.AutorizacionOP.nop == nop).order_by(
        models.AutorizacionOP.fecha.desc())).first()
    if not cupo:
        raise ReglaNegocioError(f"No existe la OP N° {nop}")
    if not cupo.habilitada or cupo.cancelada or cupo.anulada:
        raise ReglaNegocioError("La OP no está habilitada")
    hoy = fecha or date.today()
    if cupo.vigencia and cupo.vigencia <= hoy:
        raise ReglaNegocioError(f"O.P. vencida ({cupo.vigencia}); no puede utilizarse")
    if sistema and cupo.sistema and cupo.sistema.strip().upper() != sistema.strip().upper():
        raise ReglaNegocioError(
            f"El sistema del pago ({sistema}) no coincide con el de la OP ({cupo.sistema})")
    if cupo.saldo < importe:
        raise ReglaNegocioError(
            f"Saldo insuficiente en la OP N° {nop}: saldo {cupo.saldo}, importe {importe}")
    cupo.importe_usado = Decimal(cupo.importe_usado) + importe
    cupo.saldo = Decimal(cupo.importe) - cupo.importe_usado
    db.commit()
    db.refresh(cupo)
    return cupo


def reintegrar_cupo(db: Session, *, nop: int, importe: Decimal) -> models.AutorizacionOP:
    """Reintegra saldo a la OP (reversa de un pago anulado)."""
    importe = Decimal(importe)
    cupo = db.scalars(select(models.AutorizacionOP).where(
        models.AutorizacionOP.nop == nop).order_by(
        models.AutorizacionOP.fecha.desc())).first()
    if not cupo:
        raise ReglaNegocioError(f"No existe la OP N° {nop}")
    cupo.importe_usado = max(Decimal("0"), Decimal(cupo.importe_usado) - importe)
    cupo.saldo = Decimal(cupo.importe) - cupo.importe_usado
    db.commit()
    db.refresh(cupo)
    return cupo


def buscar_egresos(db: Session, *, modo: str = "apellido", valor: str = "",
                   limit: int = 100, offset: int = 0) -> dict:
    """Busca transacciones de egresos (VFP: frm815050000buscaegresos / menú 81505).

    Reproduce los 7 modos del form (optiongroup1): apellido/nombre (subcadena),
    CUIL, nº recibo, nº resolución, fecha resolución, nº OP y fecha OP. Devuelve el
    total del filtro y el detalle paginado con las 11 columnas de la grilla."""
    E = models.Egreso
    valor = (valor or "").strip()
    base = select(E)
    if modo == "apellido":
        base = base.where(E.apenom.ilike(f"%{valor}%"))
        orden = E.apenom
    elif modo == "cuil":
        base = base.where(E.cuil.like(f"%{valor}%"))
        orden = E.cuil
    elif modo == "recibo":
        base = base.where(E.no_recibo == _int(valor))
        orden = E.no_recibo
    elif modo == "resolucion":
        base = base.where(E.nro_res == _int(valor))
        orden = E.nro_res
    elif modo == "fecha_res":
        base = base.where(E.fec_res == valor)
        orden = E.fec_res
    elif modo == "op":
        base = base.where(E.no_op == _int(valor))
        orden = E.no_op
    elif modo == "fecha_op":
        base = base.where(E.fecha_op == valor)
        orden = E.fecha_op
    else:
        raise ReglaNegocioError(f"Modo de búsqueda inválido: {modo}")

    sub = base.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    importe_total = Decimal(db.scalar(select(func.coalesce(func.sum(sub.c.total), 0))) or 0)
    filas = db.scalars(base.order_by(orden).limit(limit).offset(offset)).all()
    items = [{"id": e.id, "sub_tipo": e.sub_tipo, "no_liquida": e.no_liquida,
              "fecha_liqu": e.fecha_liqu, "nro_res": e.nro_res, "fec_res": e.fec_res,
              "no_credito": e.no_credito, "apenom": e.apenom, "cuil": e.cuil,
              "no_op": e.no_op, "fecha_op": e.fecha_op, "no_recibo": e.no_recibo,
              "total": e.total, "pagado": e.pagado, "anulado": e.anulado}
             for e in filas]
    return {"modo": modo, "valor": valor, "total": total, "importe_total": importe_total,
            "limit": limit, "offset": offset, "items": items}


def _int(v, d=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return d


def cheques_emitidos(db: Session, *, desde: date | None = None, hasta: date | None = None,
                     cuenta: str | None = None, banco: int | None = None,
                     incluir_anulados: bool = False, limit: int = 100, offset: int = 0) -> dict:
    """Listado de cheques emitidos (VFP: Egresos/cheques.dbf, menú 83040).

    Filtra por rango de `fecha`, tipo de chequera (`cuenta`: CREDITOS/SEGUROS/
    JUEGOS/RENTAS) y banco; por defecto excluye los anulados (LANULA). Devuelve
    total e importe del filtro, resumen por tipo de cuenta y el detalle paginado
    ordenado por fecha y nº de cheque."""
    C = models.ChequeEmitido
    base = select(C)
    if not incluir_anulados:
        base = base.where(C.anulado.is_(False))
    if desde:
        base = base.where(C.fecha >= desde)
    if hasta:
        base = base.where(C.fecha <= hasta)
    if cuenta:
        base = base.where(C.cuenta == cuenta)
    if banco is not None:
        base = base.where(C.banco == banco)

    sub = base.subquery()
    total = db.scalar(select(func.count()).select_from(sub)) or 0
    importe_total = Decimal(db.scalar(
        select(func.coalesce(func.sum(sub.c.importe), 0))) or 0)

    # Resumen por tipo de cuenta (sobre el mismo filtro).
    res_q = base.with_only_columns(C.cuenta, func.count(), func.coalesce(func.sum(C.importe), 0)) \
                .group_by(C.cuenta).order_by(C.cuenta)
    resumen = [{"cuenta": c or "—", "cantidad": n, "importe": Decimal(imp)}
               for c, n, imp in db.execute(res_q).all()]

    filas = db.scalars(base.order_by(C.fecha, C.ncheque).limit(limit).offset(offset)).all()
    items = [{"id": c.id, "banco": c.banco, "ncuenta": c.ncuenta, "cuenta": c.cuenta,
              "ncheque": c.ncheque, "fecha": c.fecha, "importe": c.importe,
              "nop": c.nop, "nres": c.nres, "nliqui": c.nliqui, "anulado": c.anulado}
             for c in filas]
    return {"total": total, "importe_total": importe_total, "limit": limit, "offset": offset,
            "resumen": resumen, "items": items}
