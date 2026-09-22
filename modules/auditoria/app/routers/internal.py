"""API interna: por acá registran el gateway (cada operación que modifica datos) y los módulos
(el detalle del registro tocado). No sale del gateway."""
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import api_interna
from app.services import registro

router = APIRouter(prefix="/internal/auditoria", tags=["internal"], dependencies=[Depends(api_interna)])


class EventoIn(BaseModel):
    usuario: str = ""
    usuario_id: int | None = None
    ip: str = ""
    modulo: str = ""
    operacion: str | None = None          # ALTA | MODIFICACION | BAJA | ACCION | ACCESO
    entidad: str = ""                     # qué registro: Contrato, Usuario, Lote…
    entidad_id: str = ""
    descripcion: str = ""
    metodo: str = ""
    ruta: str = ""
    estado_http: int | None = None
    exito: bool | None = None
    origen: str = "MODULO"                # GATEWAY | MODULO
    request_id: str = ""                  # une lo que registró el gateway con el detalle del módulo
    cambios: dict = Field(default_factory=dict)   # {campo: [antes, después]}
    detalle: str = ""
    fecha: datetime | None = None


class LoteIn(BaseModel):
    eventos: list[EventoIn] = Field(min_length=1, max_length=500)


@router.post("/eventos", status_code=201)
def registrar(data: LoteIn, db: Session = Depends(get_db)):
    """Alta de uno o varios eventos. Sólo agrega: no hay forma de editarlos ni borrarlos."""
    ids = [registro.registrar(db, e.model_dump()).id for e in data.eventos]
    db.commit()
    return {"registrados": len(data.eventos), "ids": ids}
