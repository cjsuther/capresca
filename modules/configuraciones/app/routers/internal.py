"""API interna: la consumen otros módulos (hoy Créditos) con la clave compartida. No sale del gateway.

- lectura de impuestos, índices, feriados y reglas de workflow;
- importación idempotente (migración de los datos que antes vivían en Créditos).
"""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.db.session import get_db
from app.dependencies.auth import api_interna
from app.routers.feriados import fechas_activas
from app.routers.impuestos import listar_impuestos
from app.routers.indices import listar_indices, serial as serial_indice
from app.services.workflow import ROLES, sembrar_reglas, serial_regla

router = APIRouter(prefix="/internal/configuraciones", tags=["internal"], dependencies=[Depends(api_interna)])


@router.get("/impuestos")
def impuestos(estado: str = Query("activos", pattern="^(activos|todos)$"), db: Session = Depends(get_db)):
    return {"items": listar_impuestos(db, estado)}


@router.get("/indices")
def indices(estado: str = Query("activos", pattern="^(activos|todos)$"), db: Session = Depends(get_db)):
    return {"items": listar_indices(db, estado)}


@router.get("/indices/{codigo}")
def indice(codigo: str, db: Session = Depends(get_db)):
    """Valor de un índice (tasa variable = índice + margen). También los dados de baja (con `activo`
    en false): una línea ya publicada que lo referencia no puede pasar a cotizar sólo el margen."""
    i = db.query(models.IndiceReferencia).filter_by(codigo=codigo.upper()).first()
    if not i:
        raise HTTPException(404, "Índice inexistente")
    return serial_indice(i)


@router.get("/feriados")
def feriados(pais: str = Query("AR"), desde: date = Query(...), hasta: date = Query(...),
             db: Session = Depends(get_db)):
    if hasta < desde:
        raise HTTPException(422, "Rango inválido")
    return {"pais": pais.upper(), "fechas": [f.isoformat() for f in fechas_activas(db, pais, desde, hasta)]}


@router.get("/workflow/{modulo}/{objeto}")
def regla_workflow(modulo: str, objeto: str, db: Session = Depends(get_db)):
    r = db.query(models.WorkflowRegla).filter_by(modulo=modulo, objeto=objeto.upper()).first()
    if not r:
        sembrar_reglas(db)   # objeto recién agregado al catálogo
        r = db.query(models.WorkflowRegla).filter_by(modulo=modulo, objeto=objeto.upper()).first()
    if not r:
        raise HTTPException(404, "Regla no encontrada")
    return serial_regla(r)


# ── Importación (migración desde el módulo que tenía estos datos) ──────────────────────────────
class ImpuestoImp(BaseModel):
    codigo: str
    nombre: str
    tipo: str = "IVA"
    alicuota: float = 0
    base: str = "INTERES"
    cuenta_contable: str = ""
    jurisdiccion: str = ""
    vigente_desde: date | None = None
    vigente_hasta: date | None = None
    activo: bool = True


class IndiceImp(BaseModel):
    codigo: str
    nombre: str
    valor: float = 0
    fuente: str = ""
    fecha_valor: date | None = None
    activo: bool = True


class FeriadoImp(BaseModel):
    pais: str = "AR"
    fecha: date
    nombre: str
    tipo: str = "INAMOVIBLE"
    origen: str = "MANUAL"
    activo: bool = True


class NivelImp(BaseModel):
    orden: int
    nombre: str = "Aprobación"
    rol: str = "APROBAR"
    cuatro_ojos: bool = True
    usuarios: list[dict] = []   # [{username, modo}]


class ReglaImp(BaseModel):
    objeto: str
    nombre: str = ""
    descripcion: str = ""
    activo: bool = False
    niveles: list[NivelImp] = []


class ImportarIn(BaseModel):
    modulo: str
    impuestos: list[ImpuestoImp] = []
    indices: list[IndiceImp] = []
    feriados: list[FeriadoImp] = []
    workflow: list[ReglaImp] = []


@router.post("/importar")
def importar(data: ImportarIn, db: Session = Depends(get_db)):
    """Alta/actualización idempotente por clave natural: impuestos e índices por código, feriados por
    país+fecha, reglas por módulo+objeto (los niveles de la regla se reemplazan por los importados)."""
    res = {"impuestos": 0, "indices": 0, "feriados": 0, "reglas": 0}
    for it in data.impuestos:
        cod = it.codigo.strip().upper()
        obj = db.query(models.Impuesto).filter_by(codigo=cod).first() or models.Impuesto(codigo=cod)
        for k, v in it.model_dump(exclude={"codigo"}).items():
            setattr(obj, k, Decimal(str(v)) if k == "alicuota" else v)
        db.add(obj); res["impuestos"] += 1
    for it in data.indices:
        cod = it.codigo.strip().upper()
        obj = db.query(models.IndiceReferencia).filter_by(codigo=cod).first() or models.IndiceReferencia(codigo=cod)
        for k, v in it.model_dump(exclude={"codigo"}).items():
            setattr(obj, k, Decimal(str(v)) if k == "valor" else v)
        db.add(obj); res["indices"] += 1
    for it in data.feriados:
        pais = it.pais.upper()
        obj = (db.query(models.Feriado).filter_by(pais=pais, fecha=it.fecha).first()
               or models.Feriado(pais=pais, fecha=it.fecha))
        obj.nombre, obj.tipo, obj.origen, obj.activo = it.nombre, it.tipo, it.origen, it.activo
        db.add(obj); db.flush(); res["feriados"] += 1
    for it in data.workflow:
        objeto = it.objeto.upper()
        r = (db.query(models.WorkflowRegla).filter_by(modulo=data.modulo, objeto=objeto).first()
             or models.WorkflowRegla(modulo=data.modulo, objeto=objeto))
        r.nombre, r.descripcion, r.activo = it.nombre or r.nombre or objeto, it.descripcion, it.activo
        if it.niveles:
            r.niveles.clear()
            db.flush()
            for n in sorted(it.niveles, key=lambda x: x.orden):
                rol = n.rol.upper() if n.rol.upper() in ROLES else "APROBAR"
                nivel = models.WorkflowNivel(orden=n.orden, nombre=n.nombre, rol=rol, cuatro_ojos=n.cuatro_ojos)
                for u in n.usuarios:
                    if u.get("username") and u.get("modo") in ("INCLUIR", "EXCLUIR"):
                        nivel.usuarios.append(models.WorkflowNivelUsuario(username=u["username"], modo=u["modo"]))
                r.niveles.append(nivel)
        db.add(r); res["reglas"] += 1
    db.commit()
    return res
