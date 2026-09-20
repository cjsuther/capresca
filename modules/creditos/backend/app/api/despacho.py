"""Módulo Despacho: resoluciones/disposiciones y expedientes con pases."""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.pagination import paginar
from app.deps import get_current_user, requiere_perfil
from app.services import despacho as svc
from app.reports.word import resolucion_docx
from app import models, schemas

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

router = APIRouter(prefix="/api/creditos/despacho", tags=["despacho"],
                   dependencies=[Depends(get_current_user)])

# Perfil Despacho (xDE) o Administrador
_perfil_desp = requiere_perfil("DE")


# ---------------- Modelos de resoluciones ----------------
@router.get("/modelos")
def modelos_resolucion(q: str | None = None, db: Session = Depends(get_db)):
    """Catálogo de modelos/plantillas de resolución (VFP: 10505/rtf)."""
    qy = select(models.ModeloResolucion)
    if q:
        qy = qy.where(models.ModeloResolucion.descripcion.like(f"%{q.upper()}%"))
    ms = db.scalars(qy.order_by(models.ModeloResolucion.descripcion)).all()
    # El COD_MOD legacy se repite entre tipos: el identificador único es `id` (se usa como key/valor en la UI).
    return [{"id": m.id, "codigo": m.codigo, "descripcion": m.descripcion,
             "tipo": "Disposición" if m.es_disposicion else "Resolución",
             "seguros": m.es_seguros, "tiene_plantilla": m.tiene_plantilla}
            for m in ms]


@router.get("/modelos/{modelo_id}")
def modelo_detalle(modelo_id: int, db: Session = Depends(get_db)):
    """Un modelo (por id único) con su plantilla (texto base que se copia al elegir "Modelo a utilizar")."""
    m = db.get(models.ModeloResolucion, modelo_id)
    if not m:
        raise HTTPException(404, "Modelo no encontrado")
    return _modelo_out(m)


def _modelo_out(m: models.ModeloResolucion) -> dict:
    return {"id": m.id, "codigo": m.codigo, "descripcion": m.descripcion, "plantilla": m.plantilla,
            "es_disposicion": m.es_disposicion, "es_seguros": m.es_seguros,
            "tiene_plantilla": m.tiene_plantilla, "tipo": "Disposición" if m.es_disposicion else "Resolución"}


@router.post("/modelos", status_code=201)
def crear_modelo(data: schemas.ModeloResolucionIn, db: Session = Depends(get_db),
                 _u: models.Usuario = Depends(_perfil_desp)):
    """Alta de un modelo/plantilla de resolución (editor mini-Word). El código se asigna solo."""
    es_dis = (data.tipo or "RES").upper() == "DIS"
    prox = (db.scalar(select(func.max(models.ModeloResolucion.codigo))) or 0) + 1  # código legacy = etiqueta
    m = models.ModeloResolucion(
        codigo=prox, tipo_res=3 if es_dis else 1, descripcion=data.descripcion.strip().upper()[:120],
        es_disposicion=es_dis, es_seguros=data.seguros,
        plantilla=(data.plantilla or "")[:20000], tiene_plantilla=bool((data.plantilla or "").strip()))
    db.add(m); db.commit(); db.refresh(m)
    return _modelo_out(m)


@router.put("/modelos/{modelo_id}")
def editar_modelo(modelo_id: int, data: schemas.ModeloResolucionIn, db: Session = Depends(get_db),
                  _u: models.Usuario = Depends(_perfil_desp)):
    m = db.get(models.ModeloResolucion, modelo_id)
    if not m:
        raise HTTPException(404, "Modelo no encontrado")
    es_dis = (data.tipo or "RES").upper() == "DIS"
    m.descripcion = data.descripcion.strip().upper()[:120]
    m.es_disposicion = es_dis
    m.tipo_res = 3 if es_dis else 1
    m.es_seguros = data.seguros
    m.plantilla = (data.plantilla or "")[:20000]
    m.tiene_plantilla = bool((data.plantilla or "").strip())
    db.commit(); db.refresh(m)
    return _modelo_out(m)


# ---------------- Resoluciones ----------------
@router.get("/resoluciones", response_model=schemas.Pagina[schemas.ResolucionOut])
def listar_resoluciones(
    tipo: str | None = Query(None, description="RES o DIS"),
    anio: int | None = None,
    limit: int = Query(25, le=200),
    offset: int = 0,
    sort: str = "fecha",
    order: str = "desc",
    db: Session = Depends(get_db),
):
    qy = select(models.Resolucion)
    if tipo:
        qy = qy.where(models.Resolucion.tipo == tipo.upper())
    if anio:
        qy = qy.where(models.Resolucion.anio == anio)
    columnas = {"fecha": models.Resolucion.fecha, "numero": models.Resolucion.numero,
                "anio": models.Resolucion.anio, "tipo": models.Resolucion.tipo,
                "asunto": models.Resolucion.asunto}
    return paginar(db, qy, model=models.Resolucion, columnas=columnas,
                   limit=limit, offset=offset, sort=sort, order=order)


@router.get("/resoluciones/{resol_id}", response_model=schemas.ResolucionDetalle)
def obtener_resolucion(resol_id: int, db: Session = Depends(get_db)):
    r = db.scalar(select(models.Resolucion).options(selectinload(models.Resolucion.beneficiarios))
                  .where(models.Resolucion.id == resol_id))
    if not r:
        raise HTTPException(404, "Resolución no encontrada")
    return r


@router.post("/resoluciones", response_model=schemas.ResolucionDetalle, status_code=201)
def crear_resolucion(data: schemas.ResolucionCreate, db: Session = Depends(get_db),
                     _u: models.Usuario = Depends(_perfil_desp)):
    try:
        r = svc.crear_resolucion(
            db, tipo=data.tipo, asunto=data.asunto, texto=data.texto, organo=data.organo,
            fecha=data.fecha, modelo_id=data.modelo_id, modelo_codigo=data.modelo_codigo,
            importe=data.importe, origen=data.origen,
            beneficiarios=[b.model_dump() for b in data.beneficiarios])
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
    return obtener_resolucion(r.id, db)


@router.put("/resoluciones/{resol_id}", response_model=schemas.ResolucionDetalle)
def editar_resolucion(resol_id: int, data: schemas.ResolucionUpdate, db: Session = Depends(get_db),
                      _u: models.Usuario = Depends(_perfil_desp)):
    """Edita un borrador (no cambia tipo/número/año; sólo si aún no es oficial)."""
    try:
        r = svc.editar_resolucion(
            db, resol_id=resol_id, fecha=data.fecha, modelo_id=data.modelo_id,
            modelo_codigo=data.modelo_codigo, texto=data.texto, importe=data.importe,
            origen=data.origen, beneficiarios=[b.model_dump() for b in data.beneficiarios])
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))
    return obtener_resolucion(r.id, db)


@router.post("/resoluciones/{resol_id}/numero-real", response_model=schemas.ResolucionOut)
def cargar_numero_real(resol_id: int, data: schemas.NumeroRealIn, db: Session = Depends(get_db),
                       _u: models.Usuario = Depends(_perfil_desp)):
    """Carga el Nº Real oficial (pantalla VFP "Carga Nº Real de RESOLUCIÓN")."""
    try:
        return svc.asignar_numero_real(db, resol_id, fecha_real=data.fecha_real)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.post("/resoluciones/{resol_id}/firmar", response_model=schemas.ResolucionOut)
def firmar_resolucion(resol_id: int, db: Session = Depends(get_db),
                      _u: models.Usuario = Depends(_perfil_desp)):
    try:
        return svc.firmar_resolucion(db, resol_id)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))


@router.get("/resoluciones/{resol_id}/word")
def resolucion_word(resol_id: int, db: Session = Depends(get_db)):
    """Genera el documento Word (.docx) de la resolución/disposición."""
    r = db.get(models.Resolucion, resol_id)
    if not r:
        raise HTTPException(404, "Resolución no encontrada")
    docx = resolucion_docx(r)
    nombre = f"{r.tipo}_{r.numero}_{r.anio}.docx"
    return Response(content=docx, media_type=DOCX,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# ---------------- Anexo de Resolución (reconstruido del fuente VFP 120100000anexo_res_dis) ----------------
@router.get("/anexo/tipos")
def anexo_tipos():
    """Tipos de anexo (AGAP, Microcréditos, Productivos, Vivienda, Gas, Resto)."""
    return [{"tipo": k, "nombre": v["nombre"]} for k, v in svc.TIPO_ANEXO.items()]


@router.get("/anexo/solicitudes")
def anexo_solicitudes(tipo: int = 6, lote: int | None = None, db: Session = Depends(get_db)):
    """Solicitudes candidatas al anexo del tipo, o las de un lote (reimpresión)."""
    return svc.solicitudes_para_anexo(db, tipo, lote=lote)


@router.post("/anexo/asignar")
def anexo_asignar(data: schemas.AnexoAsignar, db: Session = Depends(get_db),
                  _u: models.Usuario = Depends(_perfil_desp)):
    """Asigna las solicitudes a la resolución (lote = N° correlativo), marca en_reso."""
    try:
        return svc.asignar_anexo(db, tipo=data.tipo, numero=data.numero,
                                 fecha=data.fecha, solicitud_ids=data.solicitud_ids)
    except svc.ReglaNegocioError as e:
        raise HTTPException(422, str(e))


@router.get("/anexo/excel")
def anexo_excel(tipo: int, lote: int, db: Session = Depends(get_db)):
    """Imprime el anexo (listado de solicitudes del lote con capital y total)."""
    from app.reports.excel import anexo_resolucion_excel
    data = svc.solicitudes_para_anexo(db, tipo, lote=lote)
    xlsx = anexo_resolucion_excel(data, lote)
    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return Response(content=xlsx, media_type=XLSX, headers={
        "Content-Disposition": f'attachment; filename="anexo_resolucion_{lote}.xlsx"'})


# ---------------- Expedientes ----------------
@router.get("/expedientes", response_model=list[schemas.ExpedienteOut])
def listar_expedientes(estado: str | None = None, db: Session = Depends(get_db)):
    qy = select(models.Expediente)
    if estado:
        qy = qy.where(models.Expediente.estado == estado)
    return db.scalars(qy.order_by(models.Expediente.id.desc())).all()


@router.get("/expedientes-por-oficina")
def expedientes_por_oficina(db: Session = Depends(get_db)):
    """Trámites/expedientes en trámite agrupados por oficina actual
    (VFP: frm530100000lista_tram_pend_ofi)."""
    from collections import defaultdict
    exps = db.scalars(select(models.Expediente).where(
        models.Expediente.estado == "T")).all()
    por_of = defaultdict(list)
    for e in exps:
        por_of[e.oficina_actual or "(sin oficina)"].append(
            {"numero": e.numero, "caratula": e.caratula, "fecha_inicio": e.fecha_inicio})
    return [{"oficina": of, "cantidad": len(items), "expedientes": items}
            for of, items in sorted(por_of.items())]


@router.get("/expedientes/{exp_id}", response_model=schemas.ExpedienteDetalle)
def obtener_expediente(exp_id: int, db: Session = Depends(get_db)):
    exp = db.scalar(select(models.Expediente)
                    .options(selectinload(models.Expediente.pases))
                    .where(models.Expediente.id == exp_id))
    if not exp:
        raise HTTPException(404, "Expediente no encontrado")
    exp.pases.sort(key=lambda p: p.orden)
    return exp


@router.post("/expedientes", response_model=schemas.ExpedienteDetalle, status_code=201)
def crear_expediente(data: schemas.ExpedienteCreate, db: Session = Depends(get_db),
                     _u: models.Usuario = Depends(_perfil_desp)):
    try:
        exp = svc.crear_expediente(db, numero=data.numero, caratula=data.caratula,
                                   iniciador=data.iniciador,
                                   oficina_inicial=data.oficina_inicial, fecha=data.fecha)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))
    return obtener_expediente(exp.id, db)


@router.post("/expedientes/{exp_id}/pase", response_model=schemas.ExpedienteDetalle)
def pasar_expediente(exp_id: int, req: schemas.PaseRequest, db: Session = Depends(get_db),
                     user: models.Usuario = Depends(_perfil_desp)):
    try:
        svc.pasar_expediente(db, exp_id, oficina_destino=req.oficina_destino,
                             motivo=req.motivo, usuario=user.username, fecha=req.fecha)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))
    return obtener_expediente(exp_id, db)


@router.post("/expedientes/{exp_id}/archivar", response_model=schemas.ExpedienteOut)
def archivar_expediente(exp_id: int, db: Session = Depends(get_db),
                        user: models.Usuario = Depends(_perfil_desp)):
    try:
        return svc.archivar_expediente(db, exp_id, user.username)
    except svc.ReglaNegocioError as e:
        raise HTTPException(409, str(e))
