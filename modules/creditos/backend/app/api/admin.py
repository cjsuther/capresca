"""Configuración del circuito de créditos: líneas, organismos (consulta) y parámetros.

Reemplaza la Administración de Líneas de Créditos (frm305050000lineas) y los parámetros del módulo.
Las demás tablas maestras de CCyPP (proveedores, compañías, requisitos, gasistas, montos por período)
y la consulta de auditoría no se migraron a Portezuelo. El acceso lo decide el gateway (`creditos`).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import requiere_perfil
from app import models, schemas


router = APIRouter(prefix="/api/creditos/admin", tags=["admin"],
                   dependencies=[Depends(requiere_perfil("AD"))])  # ADMG siempre pasa


# ---------------- Líneas de crédito ----------------
@router.get("/lineas", response_model=list[schemas.LineaAdminOut])
def lineas(db: Session = Depends(get_db)):
    return db.scalars(select(models.LineaCredito).order_by(models.LineaCredito.nombre)).all()


@router.post("/lineas", response_model=schemas.LineaAdminOut, status_code=201)
def crear_linea(data: schemas.LineaCreate, db: Session = Depends(get_db)):
    linea = models.LineaCredito(**data.model_dump())
    db.add(linea)
    db.commit()
    db.refresh(linea)
    return linea


@router.put("/lineas/{linea_id}", response_model=schemas.LineaAdminOut)
def editar_linea(linea_id: int, data: schemas.LineaCreate, db: Session = Depends(get_db)):
    linea = db.get(models.LineaCredito, linea_id)
    if not linea:
        raise HTTPException(404, "Línea no encontrada")
    for k, v in data.model_dump().items():
        setattr(linea, k, v)
    db.commit()
    db.refresh(linea)
    return linea


# ---------------- Organismos ----------------
@router.get("/organismos", response_model=list[schemas.OrganismoAdminOut])
def organismos(db: Session = Depends(get_db)):
    return db.scalars(select(models.Organismo).order_by(models.Organismo.nombre)).all()


# ---------------- Parámetros ----------------
@router.get("/parametros", response_model=list[schemas.ParametroOut])
def parametros(ambito: str | None = None, db: Session = Depends(get_db)):
    """Parámetros. Filtrables por ámbito (general|creditos|contabilidad) — H-197."""
    qy = select(models.Parametro)
    if ambito:
        qy = qy.where(models.Parametro.ambito == ambito)
    return db.scalars(qy.order_by(models.Parametro.clave)).all()


@router.post("/parametros", response_model=schemas.ParametroOut, status_code=201)
def upsert_parametro(data: schemas.ParametroUpsert, db: Session = Depends(get_db)):
    p = db.scalar(select(models.Parametro).where(models.Parametro.clave == data.clave))
    if p:
        p.valor = data.valor
        p.descripcion = data.descripcion
        if data.ambito:
            p.ambito = data.ambito
    else:
        p = models.Parametro(**data.model_dump())
        db.add(p)
    db.commit()
    db.refresh(p)
    return p
