from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from app.db.session import get_db
from app.dependencies.auth import get_current_user_id
from app.models.batch import LiquidacionBatch
from app.models.procesada import LiquidacionProcesada
from app.models.validacion import LiquidacionValidacion
from app.models.archivo import LiquidacionArchivo
from app.models.detalle_raw import LiquidacionDetalleRaw
from app.schemas.liquidacion import (
    ProcessRequest, BatchResponse, ProcesadaResponse,
    ValidacionResponse, ArchivoResponse, DetalleRawResponse,
)
from app.services.processing import process_from_path, process_from_upload
from app.services.conciliacion_client import send_to_conciliacion

router = APIRouter()


@router.post("/process", response_model=BatchResponse)
def process_zip(
    request: ProcessRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    batch = process_from_path(db, request.zip_path, user_id)
    return batch


@router.post("/upload", response_model=BatchResponse)
async def upload_zip(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un ZIP")
    content = await file.read()
    batch = process_from_upload(db, content, file.filename, user_id)
    return batch


@router.get("/batches", response_model=list[BatchResponse])
def list_batches(
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    query = db.query(LiquidacionBatch).order_by(LiquidacionBatch.created_at.desc())
    if status:
        query = query.filter(LiquidacionBatch.status == status)
    if date_from:
        query = query.filter(LiquidacionBatch.operation_date >= date_from)
    if date_to:
        query = query.filter(LiquidacionBatch.operation_date <= date_to)
    return query.offset(offset).limit(limit).all()


@router.get("/batches/{batch_id}", response_model=BatchResponse)
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    batch = db.query(LiquidacionBatch).filter(LiquidacionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    return batch


@router.get("/batches/{batch_id}/detalle", response_model=list[ProcesadaResponse])
def get_batch_detalle(
    batch_id: int,
    agency: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    query = db.query(LiquidacionProcesada).filter(LiquidacionProcesada.batch_id == batch_id)
    if agency:
        query = query.filter(LiquidacionProcesada.n_agen == agency)
    return query.order_by(LiquidacionProcesada.n_agen, LiquidacionProcesada.c_juego).all()


@router.get("/batches/{batch_id}/validaciones", response_model=list[ValidacionResponse])
def get_batch_validaciones(
    batch_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return db.query(LiquidacionValidacion).filter(
        LiquidacionValidacion.batch_id == batch_id
    ).order_by(LiquidacionValidacion.id).all()


@router.get("/batches/{batch_id}/archivos", response_model=list[ArchivoResponse])
def list_batch_archivos(
    batch_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return db.query(
        LiquidacionArchivo.id,
        LiquidacionArchivo.batch_id,
        LiquidacionArchivo.file_type,
        LiquidacionArchivo.original_filename,
        LiquidacionArchivo.file_size,
        LiquidacionArchivo.created_at,
    ).filter(LiquidacionArchivo.batch_id == batch_id).all()


@router.get("/batches/{batch_id}/archivos/{archivo_id}")
def download_archivo(
    batch_id: int,
    archivo_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    archivo = db.query(LiquidacionArchivo).filter(
        LiquidacionArchivo.id == archivo_id,
        LiquidacionArchivo.batch_id == batch_id,
    ).first()
    if not archivo:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    content_type_map = {
        "ZIP": "application/zip",
        "PDF_MOVIMIENTOS": "application/pdf",
        "PDF_RESUMENES": "application/pdf",
        "DBF_DETALLE": "application/octet-stream",
        "DBF_RESUMEN": "application/octet-stream",
    }
    content_type = content_type_map.get(archivo.file_type, "application/octet-stream")

    return StreamingResponse(
        io.BytesIO(archivo.file_data),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{archivo.original_filename}"'},
    )


@router.get("/batches/{batch_id}/raw", response_model=list[DetalleRawResponse])
def get_batch_raw(
    batch_id: int,
    agency: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    query = db.query(LiquidacionDetalleRaw).filter(LiquidacionDetalleRaw.batch_id == batch_id)
    if agency:
        query = query.filter(LiquidacionDetalleRaw.n_agen == agency)
    return query.order_by(LiquidacionDetalleRaw.id).offset(offset).limit(limit).all()


@router.post("/batches/{batch_id}/retry-conciliacion", response_model=BatchResponse)
def retry_conciliacion(
    batch_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    batch = db.query(LiquidacionBatch).filter(LiquidacionBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Lote no encontrado")
    if batch.status != "VALIDADO":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede reenviar un lote en estado VALIDADO (estado actual: {batch.status})"
        )

    try:
        send_to_conciliacion(db, batch)
        batch.status = "ENVIADO_CONCILIACION"
        batch.sent_to_conciliacion_at = datetime.now()
        batch.error_message = None
        db.commit()
    except Exception as e:
        batch.error_message = f"Error al enviar a conciliación: {str(e)}"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    return batch
