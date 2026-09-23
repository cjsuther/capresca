"""Importación del padrón de clientes (maeclientes.dbf del sistema anterior).

La subida responde enseguida y el archivo se procesa en segundo plano: son ~78.000 registros y el
gateway corta cualquier request a los 120 s. La pantalla consulta `GET …/{id}` para ver el avance.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.models import ClientImport, IMPORT_PENDIENTE, IMPORT_PROCESANDO
from app.services import padron_import

router = APIRouter(tags=["padron"])
log = logging.getLogger("clientes.padron")

MAX_BYTES = 200 * 1024 * 1024        # el DBF sin comprimir ronda los 50 MB; el ZIP, 10 MB
EXTENSIONES = (".zip", ".dbf")


def _serial(i: ClientImport) -> dict:
    return {
        "id": i.id, "archivo": i.archivo, "tamano": i.tamano, "estado": i.estado,
        "total": i.total, "procesados": i.procesados, "creados": i.creados,
        "actualizados": i.actualizados, "rechazados": i.rechazados,
        "porcentaje": round(i.procesados * 100 / i.total, 1) if i.total else 0.0,
        "mensaje": i.mensaje, "usuarioId": i.usuario_id,
        "creadoEn": i.creado_en.isoformat() if i.creado_en else None,
        "terminadoEn": i.terminado_en.isoformat() if i.terminado_en else None,
    }


@router.post("/padron/importaciones", status_code=201)
def subir(file: UploadFile = File(...), db: Session = Depends(get_db),
          user_id: int = Depends(get_current_user_id)):
    """Recibe el ZIP (o el DBF suelto) y arranca la importación en segundo plano."""
    nombre = os.path.basename(file.filename or "padron")
    if not nombre.lower().endswith(EXTENSIONES):
        raise HTTPException(422, "Subí el padrón en .zip o el .dbf directamente.")
    # Una sola importación a la vez: dos corriendo juntas se pisan al unificar por CUIL.
    if db.query(ClientImport.id).filter(
            ClientImport.estado.in_([IMPORT_PENDIENTE, IMPORT_PROCESANDO])).first():
        raise HTTPException(409, "Ya hay una importación en curso. Esperá a que termine.")

    os.makedirs(padron_import.DIR_IMPORTS, exist_ok=True)
    imp = ClientImport(archivo=nombre, tamano=0, estado=IMPORT_PENDIENTE, usuario_id=user_id)
    db.add(imp)
    db.commit()
    db.refresh(imp)

    ruta = os.path.join(padron_import.DIR_IMPORTS, f"{imp.id}-{nombre}")
    sha = hashlib.sha256()
    tamano = 0
    try:
        with open(ruta, "wb") as f:
            while True:
                chunk = file.file.read(1024 * 1024)     # de a 1 MB: no entra entero en memoria
                if not chunk:
                    break
                tamano += len(chunk)
                if tamano > MAX_BYTES:
                    raise HTTPException(413, "El archivo supera los 200 MB.")
                sha.update(chunk)
                f.write(chunk)
    except HTTPException:
        os.path.exists(ruta) and os.remove(ruta)
        db.delete(imp)
        db.commit()
        raise
    imp.tamano, imp.sha256 = tamano, sha.hexdigest()
    db.commit()

    # Hilo aparte: el request contesta ya y la importación sigue sola.
    threading.Thread(target=padron_import.procesar, args=(imp.id, ruta),
                     name=f"padron-{imp.id}", daemon=True).start()
    db.refresh(imp)
    return _serial(imp)


@router.get("/padron/importaciones")
def listar(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    filas = (db.query(ClientImport).order_by(ClientImport.id.desc()).limit(limit).all())
    return {"items": [_serial(f) for f in filas]}


@router.get("/padron/importaciones/{import_id}")
def ver(import_id: int, db: Session = Depends(get_db)):
    imp = db.get(ClientImport, import_id)
    if imp is None:
        raise HTTPException(404, "Importación no encontrada")
    return _serial(imp)


@router.get("/padron/importaciones/{import_id}/rechazos")
def rechazos(import_id: int, db: Session = Depends(get_db)):
    """Los registros que quedaron afuera, en CSV para corregirlos en el origen y volver a subir."""
    imp = db.get(ClientImport, import_id)
    if imp is None:
        raise HTTPException(404, "Importación no encontrada")
    csv_txt = padron_import.rechazos_csv(db, import_id)
    return Response(content=csv_txt.encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition":
                             f'attachment; filename="rechazos-importacion-{import_id}.csv"'})
