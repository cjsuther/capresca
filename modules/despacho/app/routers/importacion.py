"""Importación de los DBF del sistema anterior (modelos, resoluciones y beneficiarios).

La subida responde enseguida y el archivo se procesa en segundo plano: el gateway corta cualquier
request a los 120 s. La pantalla consulta el avance.
"""
from __future__ import annotations

import logging
import os
import threading

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.db.session import get_db
from app.dependencies.auth import Usuario, requiere
from app.models import IMPORT_PENDIENTE, IMPORT_PROCESANDO, ImportacionDespacho
from app.services import importacion as svc

router = APIRouter(tags=["despacho"])
log = logging.getLogger("despacho.importacion")

MAX_BYTES = 200 * 1024 * 1024
EXTENSIONES = (".zip", ".dbf")


def _serial(i: ImportacionDespacho) -> dict:
    return {
        "id": i.id, "archivo": i.archivo, "tamano": i.tamano, "estado": i.estado,
        "modelos": i.modelos, "resoluciones": i.resoluciones, "beneficiarios": i.beneficiarios,
        "omitidas": i.omitidas, "reparadas": i.reparadas, "mensaje": i.mensaje or "",
        "creadoEn": i.creado_en, "terminadoEn": i.terminado_en,
    }


@router.post("/importaciones", response_model=schemas.ImportacionOut, status_code=201)
def subir(file: UploadFile = File(...), db: Session = Depends(get_db),
          u: Usuario = Depends(requiere("importar"))):
    nombre = os.path.basename(file.filename or "despacho")
    if not nombre.lower().endswith(EXTENSIONES):
        raise HTTPException(422, "Subí los archivos del sistema anterior en .zip (o un .dbf suelto).")
    if db.scalar(select(ImportacionDespacho.id).where(
            ImportacionDespacho.estado.in_([IMPORT_PENDIENTE, IMPORT_PROCESANDO]))):
        raise HTTPException(409, "Ya hay una importación en curso. Esperá a que termine.")

    os.makedirs(svc.DIR_IMPORTS, exist_ok=True)
    imp = ImportacionDespacho(archivo=nombre, tamano=0, estado=IMPORT_PENDIENTE, usuario_id=u.user_id)
    db.add(imp)
    db.commit()
    db.refresh(imp)

    ruta = os.path.join(svc.DIR_IMPORTS, f"{imp.id}-{nombre}")
    tamano = 0
    try:
        with open(ruta, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                tamano += len(chunk)
                if tamano > MAX_BYTES:
                    raise HTTPException(413, "El archivo supera los 200 MB.")
                f.write(chunk)
    except HTTPException:
        os.path.exists(ruta) and os.remove(ruta)
        db.delete(imp)
        db.commit()
        raise
    imp.tamano = tamano
    db.commit()

    threading.Thread(target=svc.procesar, args=(imp.id, ruta),
                     name=f"despacho-import-{imp.id}", daemon=True).start()
    db.refresh(imp)
    return _serial(imp)


@router.get("/importaciones", response_model=schemas.ListaImportaciones)
def listar(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
           _u: Usuario = Depends(requiere("importar"))):
    filas = db.scalars(select(ImportacionDespacho)
                       .order_by(ImportacionDespacho.id.desc()).limit(limit)).all()
    return {"items": [_serial(f) for f in filas]}


@router.get("/importaciones/{import_id}", response_model=schemas.ImportacionOut)
def ver(import_id: int, db: Session = Depends(get_db), _u: Usuario = Depends(requiere("importar"))):
    imp = db.get(ImportacionDespacho, import_id)
    if imp is None:
        raise HTTPException(404, "Importación no encontrada")
    return _serial(imp)
