"""Módulo Caja: consulta de cuotas pendientes y cobranza con emisión de recibo."""
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.idempotency import con_idempotencia
from app.deps import get_current_user, requiere_perfil
from app.services import auditoria as audit
from app.services import caja as svc
from app.reports.pdf import (recibo_pdf, cierre_caja_pdf, pendientes_cobro_pdf,
                             control_caja_pdf, recibo_reimpresion_pdf)
from app import models, schemas

router = APIRouter(prefix="/api/creditos/caja", tags=["caja"],
                   dependencies=[Depends(get_current_user)])


@router.get("/creditos/{credito_id}/pendientes",
            response_model=list[schemas.CuotaPendienteOut])
def pendientes(
    credito_id: int,
    fecha_pago: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    try:
        return svc.cuotas_pendientes(db, credito_id, fecha_pago)
    except svc.ReglaNegocioError as e:
        raise HTTPException(404, str(e))


def _recibo_detalle(db: Session, r: models.Recibo) -> schemas.ReciboDetalle:
    cliente = db.get(models.Cliente, r.cliente_id)
    pagos = db.scalars(select(models.PagoCuota).where(
        models.PagoCuota.recibo_id == r.id)).all()
    return schemas.ReciboDetalle(
        **schemas.ReciboOut.model_validate(r).model_dump(),
        cliente_nombre=cliente.apellido_nombre if cliente else "",
        pagos=[schemas.PagoCuotaOut.model_validate(p) for p in pagos],
    )


@router.post("/cobrar", response_model=schemas.ReciboDetalle, status_code=201)
def cobrar(
    req: schemas.CobranzaRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(requiere_perfil("CJ", "TE")),  # Caja/Tesorería o ADMG
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    ip = audit.ip_de(request)

    def _do():   # H-154: dinero → idempotente. Un doble-POST con la misma clave no genera dos recibos.
        try:
            recibo = svc.cobrar(db, req.credito_id, req.cuotas, req.fecha_pago,
                                req.via_pago, cajero=user.username)
        except svc.ReglaNegocioError as e:
            audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                                   entidad="Recibo", operacion="COBRAR", resultado="RECHAZADO",
                                   despues={"credito_id": req.credito_id, "cuotas": req.cuotas,
                                            "via_pago": req.via_pago},
                                   detalle=f"Cobranza rechazada: {e}")
            raise HTTPException(409, str(e))
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Recibo", entidad_id=recibo.numero, operacion="COBRAR", resultado="OK",
                               despues={"recibo_id": recibo.id, "numero": recibo.numero,
                                        "credito_id": req.credito_id, "total": str(recibo.total),
                                        "via_pago": req.via_pago},
                               detalle=f"Cobranza recibo {recibo.numero} sobre crédito {req.credito_id}")
        return {"recibo_id": recibo.id}

    res = con_idempotencia(db, idempotency_key, "POST /api/caja/cobrar", _do, usuario=user.username)
    return _recibo_detalle(db, db.get(models.Recibo, res["recibo_id"]))


@router.get("/cola", response_model=schemas.ColaCaja)
def cola_de_caja(
    cuil: str | None = Query(default=None),
    dni: str | None = Query(default=None),
    nombre: str | None = Query(default=None),
    fecha: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
):
    """Cola de caja de una persona (créditos + cuotas pendientes con mora),
    buscando por CUIL, DNI o nombre. VFP: frm225150000cresegu1 (menú 22515)."""
    try:
        return svc.cola_de_caja(db, fecha=fecha, cuil=cuil, dni=dni, nombre=nombre)
    except svc.ReglaNegocioError as e:
        raise HTTPException(400, str(e))


@router.post("/cola/cobrar", response_model=schemas.ReciboDetalle, status_code=201)
def cobrar_cola(
    req: schemas.ColaCobroRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: models.Usuario = Depends(requiere_perfil("CJ", "TE")),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    """Cobra una selección de la cola (varios créditos de la misma persona) en un
    solo recibo."""
    ip = audit.ip_de(request)

    def _do():   # H-154: idempotente (dinero)
        try:
            recibo = svc.cobrar_cola(
                db, items=[it.model_dump() for it in req.items],
                fecha_pago=req.fecha_pago, via_pago=req.via_pago, cajero=user.username)
        except svc.ReglaNegocioError as e:
            audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                                   entidad="Recibo", operacion="COBRAR", resultado="RECHAZADO",
                                   despues={"items": len(req.items), "via_pago": req.via_pago},
                                   detalle=f"Cobranza de cola rechazada: {e}")
            raise HTTPException(409, str(e))
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Recibo", entidad_id=recibo.numero, operacion="COBRAR", resultado="OK",
                               despues={"recibo_id": recibo.id, "numero": recibo.numero,
                                        "total": str(recibo.total), "creditos": len(req.items),
                                        "via_pago": req.via_pago},
                               detalle=f"Cobranza de cola recibo {recibo.numero} ({len(req.items)} crédito/s)")
        return {"recibo_id": recibo.id}

    res = con_idempotencia(db, idempotency_key, "POST /api/caja/cola/cobrar", _do, usuario=user.username)
    return _recibo_detalle(db, db.get(models.Recibo, res["recibo_id"]))


@router.get("/recibos/{recibo_id}", response_model=schemas.ReciboDetalle)
def obtener_recibo(recibo_id: int, db: Session = Depends(get_db)):
    r = db.get(models.Recibo, recibo_id)
    if not r:
        raise HTTPException(404, "Recibo no encontrado")
    return _recibo_detalle(db, r)


@router.post("/recibos/{recibo_id}/anular", response_model=schemas.ReciboDetalle)
def anular_recibo(recibo_id: int, request: Request, db: Session = Depends(get_db),
                  user: models.Usuario = Depends(requiere_perfil("CJ", "TE"))):
    """Anula un recibo y revierte la cobranza (cuotas y saldo del crédito)."""
    ip = audit.ip_de(request)
    prev = db.get(models.Recibo, recibo_id)
    antes = {"numero": prev.numero, "estado": prev.estado, "total": str(prev.total)} if prev else None
    try:
        r = svc.anular_recibo(db, recibo_id)
    except svc.ReglaNegocioError as e:
        audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                               entidad="Recibo", entidad_id=recibo_id, operacion="ANULAR",
                               resultado="RECHAZADO", antes=antes, detalle=f"Anulación rechazada: {e}")
        raise HTTPException(409, str(e))
    audit.registrar_cambio(db, usuario=user.username, perfil=user.perfil, ip=ip,
                           entidad="Recibo", entidad_id=r.numero, operacion="ANULAR", resultado="OK",
                           antes=antes, despues={"estado": r.estado},
                           detalle=f"Recibo {r.numero} anulado (cobranza revertida)")
    return _recibo_detalle(db, r)


@router.get("/recibos/{recibo_id}/pdf")
def recibo_pdf_endpoint(recibo_id: int, db: Session = Depends(get_db)):
    r = db.get(models.Recibo, recibo_id)
    if not r:
        raise HTTPException(404, "Recibo no encontrado")
    cliente = db.get(models.Cliente, r.cliente_id)
    pagos = db.scalars(select(models.PagoCuota).where(
        models.PagoCuota.recibo_id == r.id)).all()
    pdf = recibo_pdf(r, pagos, cliente.apellido_nombre if cliente else "")
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recibo_{r.numero}.pdf"'},
    )


@router.get("/control", response_model=schemas.ControlCaja)
def control_caja(
    fecha: date = Query(default_factory=date.today),
    cajero: str | None = None,
    db: Session = Depends(get_db),
):
    return svc.control_caja(db, fecha, cajero)


@router.get("/control/pdf")
def control_caja_pdf_endpoint(
    fecha: date = Query(default_factory=date.today),
    cajero: str | None = None,
    db: Session = Depends(get_db),
):
    data = svc.control_caja(db, fecha, cajero)
    pdf = control_caja_pdf(data)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="control_caja_{fecha}.pdf"'})


@router.get("/pendientes-cobro", response_model=schemas.PendientesCobro)
def pendientes_cobro(
    fecha_corte: date = Query(default_factory=date.today),
    solo_vencidas: bool = True,
    db: Session = Depends(get_db),
):
    return svc.pendientes_cobro(db, fecha_corte, solo_vencidas)


@router.get("/pendientes-cobro/pdf")
def pendientes_cobro_pdf_endpoint(
    fecha_corte: date = Query(default_factory=date.today),
    solo_vencidas: bool = True,
    db: Session = Depends(get_db),
):
    data = svc.pendientes_cobro(db, fecha_corte, solo_vencidas)
    pdf = pendientes_cobro_pdf(data)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="pendientes_{fecha_corte}.pdf"'})


@router.get("/recibos-del-dia", response_model=schemas.RecibosDelDia)
def recibos_del_dia(fecha: date = Query(...), db: Session = Depends(get_db)):
    """Recibos emitidos en un día (quiniela + créditos/seguros) para reimpresión (23010/23012)."""
    return svc.recibos_del_dia(db, fecha=fecha)


@router.get("/recibos-del-dia/reimprimir")
def reimprimir_recibo(no_recibo: int = Query(...), origen: str = Query(...),
                      fecha: date = Query(...), db: Session = Depends(get_db)):
    """Reimprime a PDF un recibo emitido (histórico), regenerándolo desde los datos."""
    try:
        d = svc.reimpresion_recibo(db, no_recibo=no_recibo, origen=origen, fecha=fecha)
    except svc.ReglaNegocioError as e:
        raise HTTPException(404, str(e))
    pdf = recibo_reimpresion_pdf(d["cabecera"], d["lineas"])
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="recibo_{no_recibo}.pdf"'})


@router.get("/pagos-realizados", response_model=schemas.PagosRealizados)
def pagos_realizados(desde: date = Query(...), hasta: date = Query(...),
                     coding: int | None = Query(default=None),
                     texto: str | None = Query(default=None),
                     db: Session = Depends(get_db)):
    """Listado de pagos realizados en un rango de fechas (23025)."""
    return svc.pagos_realizados(db, desde=desde, hasta=hasta, coding=coding, texto=texto)


@router.get("/planilla-contable-creditos", response_model=schemas.PlanillaContableCreditos)
def planilla_contable_creditos(fecha: date = Query(...), db: Session = Depends(get_db)):
    """Planilla para contabilidad: créditos cobrados en un día, por concepto (23045)."""
    return svc.planilla_contable_creditos(db, fecha=fecha)


@router.get("/intereses-iva-mensual", response_model=schemas.InteresesIvaMensual)
def intereses_iva_mensual(mes: int = Query(...), anio: int = Query(...),
                          db: Session = Depends(get_db)):
    """Reporte mensual de intereses e IVA (23015): créditos/seguros/extra + quiniela."""
    try:
        return svc.intereses_iva_mensual(db, mes=mes, anio=anio)
    except svc.ReglaNegocioError as e:
        raise HTTPException(400, str(e))


@router.get("/recaudacion-anual", response_model=schemas.RecaudacionAnual)
def recaudacion_anual(anio: int = Query(...), db: Session = Depends(get_db)):
    """Recaudación anual por origen y mes (23030): créditos/seguros + quiniela."""
    return svc.recaudacion_anual(db, anio=anio)


@router.get("/cobranzas-periodo", response_model=schemas.CobranzasPeriodo)
def cobranzas_periodo(
    desde: date = Query(...), hasta: date = Query(...),
    origen: str | None = Query(default=None, description="CR o JUEG"),
    db: Session = Depends(get_db),
):
    """Informe de cobranzas en un período (23065): créditos/seguros + quiniela."""
    return svc.cobranzas_periodo(db, desde=desde, hasta=hasta, origen=origen)


@router.get("/cierre", response_model=schemas.CierreCaja)
def cierre_caja(
    fecha: date = Query(default_factory=date.today),
    cajero: str | None = None,
    db: Session = Depends(get_db),
):
    """Resumen de cobranzas de un día (opcionalmente por cajero)."""
    from decimal import Decimal
    from collections import defaultdict

    qy = select(models.Recibo).where(
        models.Recibo.fecha_pago == fecha, models.Recibo.estado == "E")
    if cajero:
        qy = qy.where(models.Recibo.cajero == cajero)
    recibos = db.scalars(qy).all()

    total = sum((r.total for r in recibos), Decimal("0"))
    por_via = defaultdict(lambda: Decimal("0"))
    for r in recibos:
        por_via[r.via_pago] += r.total

    # desglose por concepto a partir de los pagos
    ids = [r.id for r in recibos]
    conc = defaultdict(lambda: Decimal("0"))
    if ids:
        pagos = db.scalars(select(models.PagoCuota).where(
            models.PagoCuota.recibo_id.in_(ids))).all()
        for p in pagos:
            conc["Capital"] += p.capital
            conc["Interés"] += p.interes
            conc["IVA"] += p.iva_interes + p.iva_punitorio
            conc["Punitorios"] += p.interes_punitorio
            conc["Seguro"] += p.seguro
            conc["Gastos adm."] += p.gastos_adm

    # Quiniela del día (cajapagos) — cierre por moneda (VFP: c_cierremoneda).
    qa = select(models.CajaPagoAgencia).where(
        models.CajaPagoAgencia.fecha_pago == fecha,
        models.CajaPagoAgencia.anulado.is_(False))
    if cajero:
        qa = qa.where(models.CajaPagoAgencia.cajero == cajero)
    pagos_ag = db.scalars(qa).all()
    quin_bonos = sum((p.cobrado_bonos for p in pagos_ag), Decimal("0"))
    quin_pesos = sum((p.cobrado_pesos for p in pagos_ag), Decimal("0"))
    quin_total = quin_bonos + quin_pesos

    # Por moneda: los recibos de créditos/seguros son pesos; la quiniela aporta ambas.
    por_moneda = {"Pesos": total + quin_pesos, "Bonos": quin_bonos}

    return schemas.CierreCaja(
        fecha=fecha, cajero=cajero, cantidad_recibos=len(recibos),
        total_cobrado=total + quin_total,
        por_via_pago=[schemas.ConceptoCierre(concepto=k, importe=v)
                      for k, v in por_via.items()],
        por_concepto=[schemas.ConceptoCierre(concepto=k, importe=v)
                      for k, v in conc.items() if v],
        por_moneda=[schemas.ConceptoCierre(concepto=k, importe=v)
                    for k, v in por_moneda.items() if v],
        quiniela_cantidad=len(pagos_ag), quiniela_cobrado=quin_total,
    )


@router.get("/cierre/pdf")
def cierre_pdf_endpoint(
    fecha: date = Query(default_factory=date.today),
    cajero: str | None = None,
    db: Session = Depends(get_db),
):
    cierre = cierre_caja(fecha=fecha, cajero=cajero, db=db)
    pdf = cierre_caja_pdf(cierre)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="cierre_{fecha}.pdf"'})
