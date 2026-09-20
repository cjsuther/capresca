"""Módulo Juegos/Quiniela: agencias y liquidaciones de agencias por sorteo."""
from datetime import date

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.idempotency import con_idempotencia
from app.core.pagination import paginar
from app.deps import get_current_user, requiere_perfil
from app.services import juegos as svc
from app import models, schemas

router = APIRouter(prefix="/api/creditos/juegos", tags=["juegos"],
                   dependencies=[Depends(get_current_user)])


@router.get("/agencias", response_model=list[schemas.AgenciaJuegoOut])
def agencias(db: Session = Depends(get_db)):
    return db.scalars(select(models.AgenciaJuego).where(models.AgenciaJuego.activa)
                      .order_by(models.AgenciaJuego.numero)).all()


@router.get("/maestro", response_model=list[schemas.JuegoOut])
def maestro_juegos(db: Session = Depends(get_db)):
    """Maestro de juegos con sus comisiones (VFP: maejuegos)."""
    return db.scalars(select(models.Juego)
                      .order_by(models.Juego.codigo, models.Juego.modalidad)).all()


@router.get("/sorteos", response_model=schemas.Pagina[schemas.SorteoOut])
def sorteos(
    cod_juego: int | None = None,
    limit: int = Query(25, le=200),
    offset: int = 0,
    sort: str = "fecha_sorteo",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    """Calendario de sorteos/jugadas con el nombre del juego (VFP: maejugadas)."""
    q = select(models.Sorteo)
    if cod_juego is not None:
        q = q.where(models.Sorteo.cod_juego == cod_juego)
    columnas = {"fecha_sorteo": models.Sorteo.fecha_sorteo,
                "no_sorteo": models.Sorteo.no_sorteo,
                "cod_juego": models.Sorteo.cod_juego,
                "fecha_vto": models.Sorteo.fecha_vto}
    res = paginar(db, q, model=models.Sorteo, columnas=columnas,
                  limit=limit, offset=offset, sort=sort, order=order)
    # Nombre del juego (modalidad base) para cada código presente en la página.
    nombres = {j.codigo: j.denominacion for j in db.scalars(
        select(models.Juego).order_by(models.Juego.modalidad.desc())).all()}
    res["items"] = [{
        "id": s.id, "cod_juego": s.cod_juego,
        "juego": nombres.get(s.cod_juego, f"Juego {s.cod_juego}"),
        "no_sorteo": s.no_sorteo, "fecha_sorteo": s.fecha_sorteo,
        "fecha_vto": s.fecha_vto, "importado_caja": s.importado_caja,
    } for s in res["items"]]
    return res


@router.get("/liquidaciones", response_model=schemas.Pagina[schemas.LiquidacionAgenciaOut])
def liquidaciones(
    no_agencia: int | None = None,
    no_sorteo: int | None = None,
    pagado: bool | None = None,
    limit: int = Query(25, le=200),
    offset: int = 0,
    sort: str = "id",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    q = select(models.LiquidacionAgencia)
    if no_agencia is not None:
        q = q.where(models.LiquidacionAgencia.no_agencia == no_agencia)
    if no_sorteo is not None:
        q = q.where(models.LiquidacionAgencia.no_sorteo == no_sorteo)
    if pagado is not None:
        q = q.where(models.LiquidacionAgencia.pagado == pagado)
    columnas = {"id": models.LiquidacionAgencia.id,
                "no_agencia": models.LiquidacionAgencia.no_agencia,
                "no_sorteo": models.LiquidacionAgencia.no_sorteo,
                "fecha_sorteo": models.LiquidacionAgencia.fecha_sorteo,
                "total": models.LiquidacionAgencia.total}
    return paginar(db, q, model=models.LiquidacionAgencia, columnas=columnas,
                   limit=limit, offset=offset, sort=sort, order=order)


@router.get("/resumen", response_model=schemas.ResumenJuegos)
def resumen(desde: date | None = None, hasta: date | None = None,
            db: Session = Depends(get_db)):
    return svc.resumen(db, desde, hasta)


@router.get("/ingresos-por-juego", response_model=list[schemas.IngresoJuegoOut])
def ingresos_por_juego(desde: date | None = None, hasta: date | None = None,
                       db: Session = Depends(get_db)):
    """Resumen de recaudación por juego (VFP: resrec, inf_ingresos_jueg)."""
    return svc.ingresos_por_juego(db, desde, hasta)


@router.post("/liquidaciones/{liq_id}/cobrar", response_model=schemas.LiquidacionAgenciaOut)
def cobrar(liq_id: int, no_recibo: int, db: Session = Depends(get_db),
           user: models.Usuario = Depends(requiere_perfil("CJ", "JU")),
           idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    def _do():   # H-157: dinero → idempotente (no cobra dos veces la liquidación).
        try:
            svc.cobrar_liquidacion(db, liq_id, user.username, no_recibo)
        except svc.ReglaNegocioError as e:
            raise HTTPException(409, str(e))
        return {"liq_id": liq_id}
    con_idempotencia(db, idempotency_key, f"POST /api/juegos/liquidaciones/{liq_id}/cobrar", _do, usuario=user.username)
    return db.get(models.LiquidacionAgencia, liq_id)


# ---------- Aplicativo de caja de quiniela (22505) ----------
@router.get("/agencias/{cod_agencia}/deuda", response_model=schemas.DeudaAgencia)
def deuda_agencia(cod_agencia: int, db: Session = Depends(get_db)):
    """Liquidaciones pendientes de una agencia, separadas por moneda (bonos/pesos)."""
    return svc.deuda_agencia(db, cod_agencia)


@router.post("/agencias/cobrar", response_model=schemas.CajaPagoAgenciaOut, status_code=201)
def cobrar_agencia(req: schemas.CobroAgenciaRequest, db: Session = Depends(get_db),
                   user: models.Usuario = Depends(requiere_perfil("CJ", "JU")),
                   idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    """Cobra la deuda de una agencia (bonos/pesos, vuelto y premios). VFP:
    frm225050000aplicaj (Aplicativo de Caja)."""
    def _do():   # H-157: dinero → idempotente (un doble-POST no duplica la cobranza de agencia).
        try:
            pago = svc.cobrar_agencia(
                db, cod_agencia=req.cod_agencia,
                formas_pago=[fp.model_dump() for fp in req.formas_pago],
                premios_bonos=req.premios_bonos, premios_pesos=req.premios_pesos,
                cajero=user.username, fecha=req.fecha)
        except svc.ReglaNegocioError as e:
            raise HTTPException(409, str(e))
        return {"id": pago.id}
    res = con_idempotencia(db, idempotency_key, "POST /api/juegos/agencias/cobrar", _do, usuario=user.username)
    return db.get(models.CajaPagoAgencia, res["id"])


@router.get("/premios-compensados", response_model=schemas.PremiosCompensados)
def premios_compensados(fecha_vto: date = Query(...), db: Session = Depends(get_db)):
    """Premios compensados por capital/interior en una fecha de vto. (23055)."""
    return svc.premios_compensados(db, fecha_vto=fecha_vto)


@router.get("/cheques-agencias", response_model=schemas.ChequesAgencias)
def cheques_agencias(fecha_vto: date = Query(...), db: Session = Depends(get_db)):
    """Listado de cheques para agencias con neto a favor (23057)."""
    return svc.cheques_agencias(db, fecha_vto=fecha_vto)


@router.get("/premios", response_model=schemas.PremiosQuiniela)
def premios_quiniela(fecha: date = Query(...),
                     modo: str = Query(default="cobradas", description="cobradas|pendientes|ambas"),
                     db: Session = Depends(get_db)):
    """Control de premios de quiniela (egresos) de un día (23020)."""
    return svc.premios_quiniela(db, fecha=fecha, modo=modo)


@router.get("/liquidaciones-cobradas", response_model=schemas.LiquidacionesCobradas)
def liquidaciones_cobradas(fecha: date = Query(...), db: Session = Depends(get_db)):
    """Liquidaciones cobradas/pagadas en un día (23050)."""
    return svc.liquidaciones_cobradas(db, fecha=fecha)


@router.get("/ingresos-brutos", response_model=schemas.IngresosBrutosPeriodo)
def ingresos_brutos(mes: int = Query(...), anio: int = Query(...),
                    db: Session = Depends(get_db)):
    """Informe de Ingresos Brutos por período (23035): retención por agencia."""
    try:
        return svc.ingresos_brutos_periodo(db, mes=mes, anio=anio)
    except svc.ReglaNegocioError as e:
        raise HTTPException(400, str(e))


@router.get("/agencias/deuda-informe", response_model=schemas.DeudaAgenciaInforme)
def deuda_agencia_informe(cod_agencia: int | None = Query(default=None),
                          desde: date | None = Query(default=None),
                          hasta: date | None = Query(default=None),
                          db: Session = Depends(get_db)):
    """Informe de deuda de agencia (22555): liquidaciones impagas por rango de
    vencimiento, con días de atraso."""
    return svc.deuda_agencia_informe(db, cod_agencia=cod_agencia, desde=desde, hasta=hasta)


@router.get("/agencia-historico")
def agencia_historico(no_agencia: int, desde: date | None = Query(default=None),
                      hasta: date | None = Query(default=None),
                      db: Session = Depends(get_db)):
    """Histórico de una agencia (cj_liqhis + cj_paghis): liquidaciones y pagos archivados."""
    return svc.agencia_historico(db, no_agencia=no_agencia, desde=desde, hasta=hasta)


@router.get("/fondo-garantia")
def fondo_garantia(cod_agencia: int | None = Query(default=None),
                   no_agencia: int | None = Query(default=None),
                   subagencia: int | None = Query(default=None),
                   desde: date | None = Query(default=None),
                   hasta: date | None = Query(default=None),
                   db: Session = Depends(get_db)):
    """Informe de Fondo de Garantía (43025): suma el fdo_gtia de las liquidaciones
    históricas + vigentes, agrupado por agencia, con detalle por juego."""
    return svc.fondo_garantia(db, cod_agencia=cod_agencia, no_agencia=no_agencia,
                              subagencia=subagencia, desde=desde, hasta=hasta)


@router.post("/agencias/pagos/{pago_id}/anular", response_model=schemas.CajaPagoAgenciaOut)
def anular_pago_agencia(pago_id: int, db: Session = Depends(get_db),
                        _u: models.Usuario = Depends(requiere_perfil("CJ", "JU"))):
    try:
        return svc.anular_pago_agencia(db, pago_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))
