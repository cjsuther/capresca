"""Módulo Tesorería / Egresos: órdenes de pago (desembolsos, seguros, proveedores)."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.idempotency import con_idempotencia
from app.core.pagination import paginar
from app.deps import get_current_user, requiere_perfil
from app.services import egresos as svc
from app.reports.pdf import recibo_reimpresion_pdf
from app import models, schemas

router = APIRouter(prefix="/api/creditos/egresos", tags=["egresos"],
                   dependencies=[Depends(get_current_user)])


@router.get("/autorizaciones", response_model=schemas.Pagina[schemas.AutorizacionOPOut])
def autorizaciones_op(
    habilitada: bool | None = Query(default=None),
    con_saldo: bool = Query(default=False),
    q: str | None = Query(default=None, description="N° de OP"),
    limit: int = Query(default=25, le=200), offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    """Maestro de OP = cupos autorizados (805100): importe autorizado, usado y saldo,
    vigencia y resolución. Paginado, con filtros por habilitada / con saldo / N°."""
    A = models.AutorizacionOP
    base = select(A)
    if habilitada is not None:
        base = base.where(A.habilitada.is_(habilitada))
    if con_saldo:
        base = base.where(A.saldo > 0)
    if q and q.strip().isdigit():
        base = base.where(A.nop == int(q.strip()))
    base = base.order_by(A.fecha.desc().nullslast(), A.nop.desc())
    return paginar(db, base, model=A, columnas={}, limit=limit, offset=offset,
                   sort=None, order="desc")


@router.get("/autorizaciones/totales")
def autorizaciones_totales(habilitada: bool | None = Query(default=None),
                           db: Session = Depends(get_db)):
    """Totales del maestro de OP: cantidad, importe autorizado, usado y saldo."""
    from sqlalchemy import func as _f
    A = models.AutorizacionOP
    q = select(_f.count(A.id), _f.coalesce(_f.sum(A.importe), 0),
               _f.coalesce(_f.sum(A.importe_usado), 0), _f.coalesce(_f.sum(A.saldo), 0))
    if habilitada is not None:
        q = q.where(A.habilitada.is_(habilitada))
    n, imp, usa, sal = db.execute(q).one()
    return {"cantidad": n, "importe": imp, "usado": usa, "saldo": sal}


@router.post("/autorizaciones/{nop}/consumir", response_model=schemas.AutorizacionOPOut)
def consumir_cupo(nop: int, req: schemas.ConsumirCupoRequest, db: Session = Depends(get_db),
                  _u: models.Usuario = Depends(requiere_perfil("TE", "AF"))):
    """Consume saldo de una OP al pagar (820100): valida vigencia/sistema/saldo y
    descuenta el importe del cupo."""
    try:
        return svc.consumir_cupo(db, nop=nop, importe=req.importe, fecha=req.fecha,
                                 sistema=req.sistema)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/autorizaciones/{nop}/reintegrar", response_model=schemas.AutorizacionOPOut)
def reintegrar_cupo(nop: int, req: schemas.ConsumirCupoRequest, db: Session = Depends(get_db),
                    _u: models.Usuario = Depends(requiere_perfil("TE", "AF"))):
    """Reintegra saldo a una OP (reversa de un pago anulado)."""
    try:
        return svc.reintegrar_cupo(db, nop=nop, importe=req.importe)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/autorizaciones", response_model=schemas.AutorizacionOPOut, status_code=201)
def crear_autorizacion_op(req: schemas.AutorizacionOPUpsert, db: Session = Depends(get_db),
                          _u: models.Usuario = Depends(requiere_perfil("TE", "AF"))):
    """Alta de una autorización/cupo de OP (805100). El saldo inicial = importe."""
    d = req.model_dump()
    a = models.AutorizacionOP(**d, importe_usado=0, saldo=d["importe"])
    db.add(a)
    db.commit(); db.refresh(a)
    return a


@router.put("/autorizaciones/{aid}", response_model=schemas.AutorizacionOPOut)
def editar_autorizacion_op(aid: int, req: schemas.AutorizacionOPUpsert,
                           db: Session = Depends(get_db),
                           _u: models.Usuario = Depends(requiere_perfil("TE", "AF"))):
    """Edición de una autorización de OP; recalcula el saldo = importe − usado."""
    a = db.get(models.AutorizacionOP, aid)
    if not a:
        raise HTTPException(404, "Autorización inexistente")
    for k, v in req.model_dump().items():
        setattr(a, k, v)
    a.saldo = Decimal(a.importe) - Decimal(a.importe_usado)
    db.commit(); db.refresh(a)
    return a


def _filtrar_op(estado, tipo, q, desde, hasta):
    qy = select(models.OrdenPago)
    if estado:
        qy = qy.where(models.OrdenPago.estado == estado)
    if tipo:
        qy = qy.where(models.OrdenPago.tipo == tipo)
    if desde:
        qy = qy.where(models.OrdenPago.fecha >= desde)
    if hasta:
        qy = qy.where(models.OrdenPago.fecha <= hasta)
    if q:
        like = f"%{q.upper()}%"
        qy = qy.where(models.OrdenPago.beneficiario.like(like)
                      | models.OrdenPago.cuit_beneficiario.like(like))
    return qy


@router.get("/ordenes", response_model=schemas.Pagina[schemas.OrdenPagoOut])
def listar(
    estado: str | None = Query(None, description="P pendiente, G girada, A anulada"),
    tipo: str | None = None,
    q: str | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    limit: int = Query(25, le=200),
    offset: int = 0,
    sort: str = "numero",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    """Informe/listado de OP con filtros (estado, tipo, beneficiario, fechas)."""
    qy = _filtrar_op(estado, tipo, q, desde, hasta)
    columnas = {"numero": models.OrdenPago.numero, "fecha": models.OrdenPago.fecha,
                "beneficiario": models.OrdenPago.beneficiario,
                "importe": models.OrdenPago.importe, "estado": models.OrdenPago.estado}
    return paginar(db, qy, model=models.OrdenPago, columnas=columnas,
                   limit=limit, offset=offset, sort=sort, order=order)


@router.get("/ordenes/excel")
def ordenes_excel(estado: str | None = None, tipo: str | None = None, q: str | None = None,
                  desde: date | None = None, hasta: date | None = None,
                  db: Session = Depends(get_db)):
    """Exporta el informe de OP filtrado (set completo) a Excel."""
    from app.reports.excel import ordenes_pago_excel
    qy = _filtrar_op(estado, tipo, q, desde, hasta).order_by(models.OrdenPago.numero.desc())
    ops = db.scalars(qy).all()
    xlsx = ordenes_pago_excel(ops)
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content=xlsx, media_type=XLSX, headers={
        "Content-Disposition": 'attachment; filename="informe_op.xlsx"'})


@router.get("/totales", response_model=schemas.TotalesEgresos)
def totales(db: Session = Depends(get_db)):
    return svc.totales(db)


@router.get("/buscar")
def buscar_egresos(modo: str = "apellido", valor: str = "",
                   limit: int = Query(100, le=500), offset: int = 0,
                   db: Session = Depends(get_db)):
    """Busca transacciones de egresos (81505) sobre el ledger real (egresos.dbf,
    340 mil): modos apellido/cuil/recibo/resolucion/fecha_res/op/fecha_op."""
    try:
        return svc.buscar_egresos(db, modo=modo, valor=valor, limit=limit, offset=offset)
    except svc.ReglaNegocioError as e:
        raise HTTPException(400, str(e))


@router.get("/cheques")
def cheques_emitidos(desde: date | None = None, hasta: date | None = None,
                     cuenta: str | None = None, banco: int | None = None,
                     incluir_anulados: bool = False,
                     limit: int = Query(100, le=500), offset: int = 0,
                     db: Session = Depends(get_db)):
    """Listado de cheques emitidos por Tesorería (83040): filtra por fecha, tipo de
    chequera y banco; resumen por cuenta + detalle paginado. Fuente: cheques.dbf."""
    return svc.cheques_emitidos(db, desde=desde, hasta=hasta, cuenta=cuenta, banco=banco,
                                incluir_anulados=incluir_anulados, limit=limit, offset=offset)


@router.get("/reporte", response_model=schemas.ReporteOP)
def reporte(desde: date | None = None, hasta: date | None = None,
            db: Session = Depends(get_db)):
    """Reporte de OP por tipo con desglose por estado (VFP: rptoprb, rptop)."""
    return svc.reporte_ordenes(db, desde, hasta)


@router.get("/ordenes/{op_id}", response_model=schemas.OrdenPagoOut)
def obtener(op_id: int, db: Session = Depends(get_db)):
    op = db.get(models.OrdenPago, op_id)
    if not op:
        raise HTTPException(404, "Orden de pago no encontrada")
    return op


@router.post("/ordenes", response_model=schemas.OrdenPagoOut, status_code=201)
def crear(
    data: schemas.OrdenPagoCreate,
    db: Session = Depends(get_db),
    _user: models.Usuario = Depends(requiere_perfil("TE", "AD")),  # Tesorería/Admin
):
    op = svc.crear_op(db, beneficiario=data.beneficiario, concepto=data.concepto,
                      importe=data.importe, tipo=data.tipo, cuit=data.cuit,
                      fecha=data.fecha)
    return op


@router.post("/ordenes/{op_id}/pagar", response_model=schemas.OrdenPagoOut)
def pagar(
    op_id: int,
    req: schemas.PagoOrdenRequest,
    db: Session = Depends(get_db),
    _user: models.Usuario = Depends(requiere_perfil("TE", "AD")),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    def _do():   # H-157: dinero → idempotente (un doble-POST no paga dos veces la OP).
        try:
            svc.pagar_op(db, op_id, banco=req.banco,
                         cheque_numero=req.cheque_numero, fecha_pago=req.fecha_pago)
        except svc.ReglaNegocioError as e:
            raise HTTPException(409, str(e))
        return {"op_id": op_id}
    con_idempotencia(db, idempotency_key, f"POST /api/egresos/ordenes/{op_id}/pagar", _do, usuario=_user.username)
    return db.get(models.OrdenPago, op_id)


@router.get("/chequeras", response_model=list[schemas.ChequeraOut])
def listar_chequeras(db: Session = Depends(get_db)):
    return db.scalars(select(models.Chequera).order_by(models.Chequera.id.desc())).all()


@router.post("/chequeras", response_model=schemas.ChequeraOut, status_code=201)
def crear_chequera(data: schemas.ChequeraCreate, db: Session = Depends(get_db),
                   _u: models.Usuario = Depends(requiere_perfil("TE", "AD"))):
    try:
        return svc.crear_chequera(db, banco=data.banco, cuenta=data.cuenta,
                                  desde=data.desde, hasta=data.hasta)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))


@router.post("/ordenes/{op_id}/pagar-chequera", response_model=schemas.OrdenPagoOut)
def pagar_con_chequera(op_id: int, req: schemas.PagoConChequera,
                       db: Session = Depends(get_db),
                       _u: models.Usuario = Depends(requiere_perfil("TE", "AD")),
                       idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    def _do():   # H-157: idempotente (no consume el cheque ni paga dos veces).
        try:
            svc.pagar_op_con_chequera(db, op_id, req.chequera_id, req.fecha_pago)
        except svc.ReglaNegocioError as e:
            raise HTTPException(409, str(e))
        return {"op_id": op_id}
    con_idempotencia(db, idempotency_key, f"POST /api/egresos/ordenes/{op_id}/pagar-chequera", _do, usuario=_u.username)
    return db.get(models.OrdenPago, op_id)


@router.get("/revision", response_model=schemas.RevisionEgresos)
def revision_egresos(db: Session = Depends(get_db)):
    """Pagos pendientes e incompletos (OP importe 0), para depuración."""
    return svc.pagos_pendientes_incompletos(db)


@router.post("/ordenes/{op_id}/anular", response_model=schemas.OrdenPagoOut)
def anular(
    op_id: int,
    db: Session = Depends(get_db),
    _user: models.Usuario = Depends(requiere_perfil("TE", "AD")),
):
    try:
        return svc.anular_op(db, op_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


# Etiquetas de tipo de egreso (VFP sub_tipo) para el comprobante.
SUBTIPO_EGRESO = {1: "Crédito", 2: "Seguro", 3: "Premio", 4: "Subsidio", 5: "Administración", 6: "Varios"}


@router.get("/{egreso_id}/comprobante-pdf")
def comprobante_egreso_pdf(egreso_id: int, db: Session = Depends(get_db)):
    """Reimpresión del comprobante de un egreso (consolida los VFP reimp* en un único visor,
    sobre el buscador de egresos existente). Usa recibo_reimpresion_pdf."""
    e = db.get(models.Egreso, egreso_id)
    if not e:
        raise HTTPException(404, "Egreso no encontrado")
    origen = SUBTIPO_EGRESO.get(e.sub_tipo, f"Tipo {e.sub_tipo}")
    extra = " · ".join(x for x in [
        f"O.P. {e.no_op}" if e.no_op else "",
        f"Resol. {e.nro_res}" if e.nro_res else "",
        f"Crédito {e.no_credito}" if e.no_credito else "",
        f"CUIL {e.cuil}" if e.cuil else "",
    ] if x)
    cabecera = {"no_recibo": e.no_recibo or e.id, "origen": f"Egreso · {origen}",
                "fecha": e.fecha_op or e.fecha_liqu or "—", "titular": e.apenom or "—",
                "cajero": "—", "extra": extra, "total": e.total}
    detalle = f"Egreso {origen}" + (" — ANULADO" if e.anulado else "")
    pdf = recibo_reimpresion_pdf(cabecera, [{"detalle": detalle, "moneda": "ARS", "importe": e.total}])
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="comprobante_egreso_{e.id}.pdf"'})
