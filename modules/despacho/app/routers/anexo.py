"""Lotes de créditos (con su resolución y el anexo impreso) y expedientes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app import schemas
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere, usuario_actual
from app.reports.word import anexo_docx
from app.services import anexo as svc
from app.services import expedientes as svc_exp
from app.services import resoluciones as svc_res

router = APIRouter(tags=["despacho"])
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# --------------------------------------------------------------------------- lotes
@router.get("/lotes/tipos")
def tipos(_u: Usuario = Depends(usuario_actual)):
    return svc.tipos()


@router.get("/lotes")
def lotes(estado: str = Query(""), tipo: str = Query(""), db: Session = Depends(get_db),
          _u: Usuario = Depends(usuario_actual)):
    return svc.listar(db, estado=estado, tipo=tipo)


@router.get("/lotes/{lote_id}")
def lote(lote_id: int, db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    return svc.ver(db, lote_id)


@router.post("/lotes/asignar")
def asignar(datos: schemas.LotesAsignarIn, db: Session = Depends(get_db),
            _u: Usuario = Depends(requiere("resoluciones:write"))):
    return svc.asignar(db, resolucion_id=datos.resolucion_id, lote_ids=datos.lote_ids)


@router.post("/lotes/{lote_id}/quitar-resolucion")
def quitar(lote_id: int, db: Session = Depends(get_db),
           _u: Usuario = Depends(requiere("resoluciones:write"))):
    return svc.quitar(db, lote_id)


@router.get("/resoluciones/{resolucion_id}/lotes")
def lotes_de_resolucion(resolucion_id: int, db: Session = Depends(get_db),
                        _u: Usuario = Depends(usuario_actual)):
    """Los lotes que otorga la resolución, lo comprometido y lo que queda de su importe."""
    return svc.comprometido(svc_res.obtener(db, resolucion_id))


@router.get("/anexo/word/{resolucion_id}")
def anexo_word(resolucion_id: int, db: Session = Depends(get_db),
               _u: Usuario = Depends(usuario_actual)):
    """El anexo impreso: el listado de solicitudes que otorga la resolución (las de sus lotes)."""
    r = svc_res.obtener(db, resolucion_id)
    filas = svc.filas_anexo(r)
    nombre = f"anexo_{r.tipo}_{r.numero_real or r.numero}_{r.anio}.docx"
    return Response(content=anexo_docx(r, filas), media_type=DOCX,
                    headers={"Content-Disposition": f'attachment; filename="{nombre}"'})


# --------------------------------------------------------------------------- expedientes
@router.get("/expedientes", response_model=list[schemas.ExpedienteOut])
def listar_expedientes(estado: str | None = None, buscar: str | None = None,
                       oficina: str | None = None, db: Session = Depends(get_db),
                       _u: Usuario = Depends(usuario_actual)):
    return svc_exp.listar(db, estado=estado, buscar=buscar, oficina=oficina)


@router.get("/expedientes-por-oficina")
def por_oficina(db: Session = Depends(get_db), _u: Usuario = Depends(usuario_actual)):
    return svc_exp.por_oficina(db)


@router.get("/expedientes/{expediente_id}", response_model=schemas.ExpedienteDetalle)
def ver_expediente(expediente_id: int, db: Session = Depends(get_db),
                   _u: Usuario = Depends(usuario_actual)):
    return svc_exp.obtener(db, expediente_id)


@router.post("/expedientes", response_model=schemas.ExpedienteDetalle, status_code=201)
def crear_expediente(datos: schemas.ExpedienteIn, db: Session = Depends(get_db),
                     u: Usuario = Depends(requiere("expedientes:write"))):
    return svc_exp.crear(db, datos, usuario=u.username)


@router.post("/expedientes/{expediente_id}/pase", response_model=schemas.ExpedienteDetalle)
def pasar(expediente_id: int, datos: schemas.PaseIn, db: Session = Depends(get_db),
          u: Usuario = Depends(requiere("expedientes:write"))):
    return svc_exp.pasar(db, expediente_id, datos, usuario=u.username)


@router.post("/expedientes/{expediente_id}/archivar", response_model=schemas.ExpedienteDetalle)
def archivar(expediente_id: int, db: Session = Depends(get_db),
             u: Usuario = Depends(requiere("expedientes:write"))):
    return svc_exp.archivar(db, expediente_id, usuario=u.username)
