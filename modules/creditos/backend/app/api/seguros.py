"""Módulo Seguros: pólizas emitidas y liquidación a la compañía aseguradora."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user, requiere_perfil
from app.services import seguros as svc
from app.services import regimenes as reg_svc
from app import models, schemas

router = APIRouter(prefix="/api/creditos/seguros", tags=["seguros"],
                   dependencies=[Depends(get_current_user)])

_perfil_seg = requiere_perfil("SE", "TE")  # Seguros/Tesorería o ADMG


@router.get("/polizas", response_model=list[schemas.PolizaOut])
def listar_polizas(
    cliente_id: int | None = None,
    credito_id: int | None = None,
    db: Session = Depends(get_db),
):
    qy = select(models.Poliza)
    if cliente_id:
        qy = qy.where(models.Poliza.cliente_id == cliente_id)
    if credito_id:
        qy = qy.where(models.Poliza.credito_id == credito_id)
    return db.scalars(qy.order_by(models.Poliza.numero.desc())).all()


@router.get("/polizas-agente")
def polizas_agente(
    q: str | None = None,
    codigo: int | None = None,
    solo_vigentes: bool = True,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Pólizas de seguro de vida colectivo por agente (VFP: seguros.dbf, 207 mil).
    Resumen por tipo + listado paginado con búsqueda por CUIL/agente/nº póliza."""
    return svc.polizas_vigentes(db, q=q, codigo=codigo, solo_vigentes=solo_vigentes,
                                limit=limit, offset=offset)


@router.get("/polizas/{poliza_id}", response_model=schemas.PolizaOut)
def obtener_poliza(poliza_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Poliza, poliza_id)
    if not p:
        raise HTTPException(404, "Póliza no encontrada")
    return p


@router.get("/liquidacion", response_model=list[schemas.LiquidacionSeguroItem])
def liquidacion(
    desde: date,
    hasta: date,
    compania_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Seguro cobrado en el período, agrupado por compañía (monto a remitir)."""
    return svc.liquidacion(db, desde, hasta, compania_id)


@router.get("/cobrados", response_model=schemas.SegurosCobrados)
def seguros_cobrados(desde: date, hasta: date, db: Session = Depends(get_db)):
    """Resumen de seguros cobrados por día en el período (frm730050000rptcobseg)."""
    return svc.seguros_cobrados(db, desde, hasta)


@router.get("/primas-devengadas", response_model=schemas.PrimasDevengadas)
def primas_devengadas(desde: date, hasta: date, db: Session = Depends(get_db)):
    """Primas de seguro devengadas/cobradas/pendientes (frm715100000cons_primas)."""
    return svc.primas_devengadas(db, desde, hasta)


@router.get("/pagos", response_model=schemas.PagosSeguros)
def pagos_seguros(desde: date, hasta: date, db: Session = Depends(get_db)):
    """Pagos de seguros emitidos (OP tipo SEGURO) en el período."""
    return svc.pagos_seguros(db, desde, hasta)


@router.get("/titulares")
def titulares(q: str | None = None, tipo: str | None = None,
              limit: int = 25, offset: int = 0, db: Session = Depends(get_db)):
    """Maestro de titulares del seguro de vida colectivo (VFP: 70505/titulares)."""
    return svc.titulares(db, q=q, tipo=tipo, limit=limit, offset=offset)


@router.get("/adicional/resumen", response_model=schemas.ResumenSeguroAdicional)
def resumen_adicional(periodo: str | None = None, db: Session = Depends(get_db)):
    """Resumen del seguro del agente por concepto (VFP: infsegadicional)."""
    return svc.resumen_seguro_adicional(db, periodo)


@router.get("/adicional/agentes", response_model=schemas.Pagina[schemas.SeguroAgenteOut])
def agentes_adicional(
    con_adicional: bool = False,
    periodo: str | None = None,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Agentes con/sin seguro de vida adicional, paginado (VFP:
    infsegadicional / informeagentessinseguroadicional)."""
    return svc.agentes_seguro_adicional(db, con_adicional=con_adicional,
                                        periodo=periodo, q=q, limit=limit, offset=offset)


# ---------------- Regímenes especiales ----------------
@router.get("/regimenes", response_model=list[schemas.RegimenOut])
def regimenes(db: Session = Depends(get_db)):
    return db.scalars(select(models.RegimenEspecial).where(
        models.RegimenEspecial.activo).order_by(models.RegimenEspecial.nombre)).all()


@router.get("/regimenes/{regimen_id}/beneficiarios",
            response_model=list[schemas.BeneficiarioOut])
def beneficiarios(regimen_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(models.Beneficiario).where(
        models.Beneficiario.regimen_id == regimen_id)
        .order_by(models.Beneficiario.apellido_nombre)).all()


@router.post("/regimenes/{regimen_id}/beneficiarios",
             response_model=schemas.BeneficiarioOut, status_code=201)
def crear_beneficiario(regimen_id: int, data: schemas.BeneficiarioCreate,
                       db: Session = Depends(get_db),
                       _u: models.Usuario = Depends(_perfil_seg)):
    try:
        return reg_svc.crear_beneficiario(
            db, regimen_id=regimen_id, apellido_nombre=data.apellido_nombre,
            cuil=data.cuil, dni=data.dni, cbu=data.cbu,
            monto_mensual=data.monto_mensual, numero_resolucion=data.numero_resolucion,
            fecha_alta=data.fecha_alta)
    except reg_svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))


@router.post("/beneficiarios/{beneficiario_id}/baja",
             response_model=schemas.BeneficiarioOut)
def baja_beneficiario(beneficiario_id: int, db: Session = Depends(get_db),
                      _u: models.Usuario = Depends(_perfil_seg)):
    try:
        return reg_svc.dar_de_baja(db, beneficiario_id)
    except reg_svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.get("/beneficiarios/{beneficiario_id}/cuotas",
            response_model=list[schemas.CuotaRegimenOut])
def cuotas_beneficiario(beneficiario_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(models.CuotaRegimen).where(
        models.CuotaRegimen.beneficiario_id == beneficiario_id)
        .order_by(models.CuotaRegimen.periodo.desc())).all()


@router.post("/regimenes/{regimen_id}/generar-cuotas",
             response_model=schemas.GeneracionCuotasOut)
def generar_cuotas(regimen_id: int, periodo: str,
                   db: Session = Depends(get_db),
                   _u: models.Usuario = Depends(_perfil_seg)):
    """Genera las cuotas del período y (regímenes de pago) las OP en Tesorería."""
    try:
        return reg_svc.generar_cuotas(db, regimen_id, periodo)
    except reg_svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
