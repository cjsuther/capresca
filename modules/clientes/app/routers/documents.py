"""Documentación del cliente: la carga el operador o llega desde otro módulo (p.ej. la solicitud de
crédito del portal). Se lista, se ve/descarga y se da de baja."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.current_user import get_current_user_id
from app.models.client import Client
from app.models.document import ClientDocument
from app.services import documentos as svc

router = APIRouter(tags=["documentos"])


def _cliente(db: Session, client_id: int) -> Client:
    c = db.query(Client).filter(Client.id == client_id).first()
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return c


def _documento(db: Session, client_id: int, doc_id: int) -> ClientDocument:
    d = db.query(ClientDocument).filter_by(id=doc_id, client_id=client_id).first()
    if not d:
        raise HTTPException(404, "Documento no encontrado")
    return d


@router.get("/{client_id}/documentos")
def listar(client_id: int, db: Session = Depends(get_db), _user: int = Depends(get_current_user_id)):
    _cliente(db, client_id)
    docs = (db.query(ClientDocument).filter_by(client_id=client_id)
            .order_by(ClientDocument.created_at.desc(), ClientDocument.id.desc()).all())
    return {"items": [svc.serial(d) for d in docs], "tipos": svc.TIPOS}


@router.post("/{client_id}/documentos", status_code=201)
async def subir(client_id: int, archivo: UploadFile = File(...), tipo: str = Form("OTRO"),
                db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    _cliente(db, client_id)
    contenido = await archivo.read()
    doc, nuevo = svc.guardar(db, client_id, contenido=contenido, nombre=archivo.filename or "documento",
                             content_type=archivo.content_type or "", tipo=tipo, user_id=user_id)
    if not nuevo:
        raise HTTPException(409, f"Ese archivo ya está cargado en el cliente ({doc.nombre}).")
    db.commit(); db.refresh(doc)
    return svc.serial(doc)


@router.get("/{client_id}/documentos/{doc_id}")
def descargar(client_id: int, doc_id: int, db: Session = Depends(get_db),
              _user: int = Depends(get_current_user_id)):
    d = _documento(db, client_id, doc_id)
    return Response(content=d.contenido, media_type=d.content_type,
                    headers={"Content-Disposition": svc.disposicion(d.nombre)})


@router.delete("/{client_id}/documentos/{doc_id}", status_code=204)
def borrar(client_id: int, doc_id: int, db: Session = Depends(get_db),
           _user: int = Depends(get_current_user_id)):
    d = _documento(db, client_id, doc_id)
    db.delete(d); db.commit()
    return Response(status_code=204)
