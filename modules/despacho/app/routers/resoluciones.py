"""Resoluciones y disposiciones, y el catálogo de modelos que las alimenta."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere, usuario_actual
from app.models import SERIES
from app.reports.word import resolucion_docx
from app.services import modelos as svc_modelos
from app.services import resoluciones as svc

router = APIRouter(tags=["despacho"])
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/series")
def series(_u: Usuario = Depends(usuario_actual)):
    """Las series de numeración: cada una lleva su propio correlativo."""
    return [{"serie": s, "nombre": n} for s, n in SERIES.items()]


# --------------------------------------------------------------------------- modelos
@router.get("/modelos", response_model=list[schemas.ModeloOut])
def listar_modelos(tipo: str | None = None, buscar: str | None = None, serie: int | None = None,
                   incluir_inactivos: bool = False, db: Session = Depends(get_db),
                   _u: Usuario = Depends(usuario_actual)):
    return svc_modelos.listar(db, tipo=tipo, buscar=buscar, serie=serie,
                              incluir_inactivos=incluir_inactivos)


@router.get("/modelos/{modelo_id}", response_model=schemas.ModeloOut)
def ver_modelo(modelo_id: int, db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    return svc_modelos.obtener(db, modelo_id)


@router.post("/modelos", response_model=schemas.ModeloOut, status_code=201)
def crear_modelo(datos: schemas.ModeloIn, db: Session = Depends(get_db),
                 _u: Usuario = Depends(requiere("modelos:write"))):
    return svc_modelos.crear(db, datos)


@router.put("/modelos/{modelo_id}", response_model=schemas.ModeloOut)
def editar_modelo(modelo_id: int, datos: schemas.ModeloIn, db: Session = Depends(get_db),
                  _u: Usuario = Depends(requiere("modelos:write"))):
    return svc_modelos.editar(db, modelo_id, datos)


# --------------------------------------------------------------------------- resoluciones
@router.get("/resoluciones", response_model=schemas.PaginaResoluciones)
def listar(tipo: str | None = None, anio: int | None = None, estado: str | None = None,
           buscar: str | None = None, serie: int | None = None, pagina: int = Query(1, ge=1),
           por_pagina: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    items, total = svc.listar(db, tipo=tipo, anio=anio, estado=estado, buscar=buscar, serie=serie,
                              pagina=pagina, por_pagina=por_pagina)
    return {"items": items, "total": total, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/resoluciones/{resolucion_id}", response_model=schemas.ResolucionDetalle)
def ver(resolucion_id: int, db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    return svc.obtener(db, resolucion_id)


@router.post("/resoluciones", response_model=schemas.ResolucionDetalle, status_code=201)
def crear(datos: schemas.ResolucionIn, db: Session = Depends(get_db),
          u: Usuario = Depends(requiere("resoluciones:write"))):
    return svc.crear(db, datos, usuario=u.username)


@router.put("/resoluciones/{resolucion_id}", response_model=schemas.ResolucionDetalle)
def editar(resolucion_id: int, datos: schemas.ResolucionUpdate, db: Session = Depends(get_db),
           _u: Usuario = Depends(requiere("resoluciones:write"))):
    return svc.editar(db, resolucion_id, datos)


@router.post("/resoluciones/{resolucion_id}/firmar", response_model=schemas.ResolucionDetalle)
def firmar(resolucion_id: int, db: Session = Depends(get_db),
           _u: Usuario = Depends(requiere("resoluciones:firmar"))):
    return svc.firmar(db, resolucion_id)


@router.post("/resoluciones/{resolucion_id}/numero-real", response_model=schemas.ResolucionDetalle)
def numero_real(resolucion_id: int, datos: schemas.NumeroRealIn, db: Session = Depends(get_db),
                _u: Usuario = Depends(requiere("resoluciones:firmar"))):
    """Carga el número OFICIAL, que llega después del correlativo."""
    return svc.asignar_numero_real(db, resolucion_id, datos.fecha_real)


@router.post("/resoluciones/{resolucion_id}/anular", response_model=schemas.ResolucionDetalle)
def anular(resolucion_id: int, datos: schemas.AnulacionIn, db: Session = Depends(get_db),
           _u: Usuario = Depends(requiere("resoluciones:firmar"))):
    return svc.anular(db, resolucion_id, datos.motivo)


@router.get("/resoluciones/{resolucion_id}/word")
def word(resolucion_id: int, db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    r = svc.obtener(db, resolucion_id)
    nombre = f"{r.tipo}_{r.numero_real or r.numero}_{r.anio}.docx"
    return Response(content=resolucion_docx(r), media_type=DOCX,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})
