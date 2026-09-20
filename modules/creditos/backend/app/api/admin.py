"""Módulo Utilidades / Tablas: ABMs de tablas maestras y configuración.

Reemplaza pantallas VFP como Administración de Líneas de Créditos
(frm305050000lineas), Consulta/ABM de Organismos, parámetros generales, etc.
El acceso lo decide el gateway por área: tablas → `general`, auditoría → `seguridad`.
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


@router.get("/proveedores", response_model=list[schemas.ProveedorOut])
def proveedores(q: str | None = None, db: Session = Depends(get_db)):
    """Maestro de proveedores (VFP: proveedores)."""
    qy = select(models.Proveedor)
    if q:
        like = f"%{q.upper()}%"
        qy = qy.where(models.Proveedor.razon_social.like(like) | models.Proveedor.cuit.like(like))
    return db.scalars(qy.order_by(models.Proveedor.razon_social)).all()


@router.post("/proveedores", response_model=schemas.ProveedorOut, status_code=201)
def crear_proveedor(data: schemas.ProveedorUpsert, db: Session = Depends(get_db)):
    p = models.Proveedor(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.post("/organismos", response_model=schemas.OrganismoAdminOut, status_code=201)
def crear_organismo(data: schemas.OrganismoUpsert, db: Session = Depends(get_db)):
    o = models.Organismo(**data.model_dump())
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


@router.put("/organismos/{org_id}", response_model=schemas.OrganismoAdminOut)
def editar_organismo(org_id: int, data: schemas.OrganismoUpsert, db: Session = Depends(get_db)):
    o = db.get(models.Organismo, org_id)
    if not o:
        raise HTTPException(404, "Organismo no encontrado")
    for k, v in data.model_dump().items():
        setattr(o, k, v)
    db.commit()
    db.refresh(o)
    return o


# ---------------- Compañías de seguros ----------------
@router.get("/companias", response_model=list[schemas.CompaniaOut])
def companias(db: Session = Depends(get_db)):
    return db.scalars(select(models.CompaniaSeguros).order_by(models.CompaniaSeguros.nombre)).all()


@router.post("/companias", response_model=schemas.CompaniaOut, status_code=201)
def crear_compania(data: schemas.CompaniaUpsert, db: Session = Depends(get_db)):
    c = models.CompaniaSeguros(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------- Parámetros generales ----------------
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


# ---------------- Usuarios, roles y permisos ----------------
# Los administra Seguridad de Portezuelo (permisos por área del módulo Créditos, ver app/core/gateway.py).
# Las tablas legacy (usuarios, perfiles, grupos, permisos por pantalla) quedan sólo como histórico del ETL.


@router.get("/auditoria")
def auditoria(
    usuario: str | None = None,
    desde: __import__("datetime").date | None = None,
    hasta: __import__("datetime").date | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Consulta paginada del log de auditoría (VFP: auditoria, rpt106auditoria)."""
    from app.services.auditoria import consultar
    return consultar(db, usuario=usuario, desde=desde, hasta=hasta,
                     limit=min(limit, 200), offset=offset)


@router.get("/auditoria/resumen")
def auditoria_resumen(
    por: str = "usuario",
    desde: __import__("datetime").date | None = None,
    hasta: __import__("datetime").date | None = None,
    db: Session = Depends(get_db),
):
    """Auditoría agrupada por usuario (X3005) o por máquina (X3010)."""
    from app.services.auditoria import resumen
    return resumen(db, por=("maquina" if por == "maquina" else "usuario"),
                   desde=desde, hasta=hasta)


# ---------------- Auditoría de cambios (sistema nuevo: antes/después + IP) ----------------
@router.get("/auditoria-cambios")
def auditoria_cambios(
    texto: str | None = None,
    entidad: str | None = None,
    operacion: str | None = None,
    resultado: str | None = None,
    desde: __import__("datetime").date | None = None,
    hasta: __import__("datetime").date | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Rastro de mutaciones del sistema nuevo (quién cambió qué, con diff e IP)."""
    from app.services.auditoria import consultar_cambios
    return consultar_cambios(db, texto=texto, entidad=entidad, operacion=operacion,
                             resultado=resultado, desde=desde, hasta=hasta,
                             limit=min(limit, 200), offset=offset)


@router.get("/auditoria-cambios/{cambio_id}")
def auditoria_cambio_detalle(cambio_id: int, db: Session = Depends(get_db)):
    """Detalle de un evento con el diff antes/después completo."""
    from app.services.auditoria import obtener_cambio
    ev = obtener_cambio(db, cambio_id)
    if not ev:
        raise HTTPException(404, "Evento de auditoría no encontrado")
    return ev


# ---------------- Requisitos de crédito ----------------
@router.get("/requisitos", response_model=list[schemas.RequisitoOut])
def requisitos(db: Session = Depends(get_db)):
    return db.scalars(select(models.Requisito).order_by(models.Requisito.id)).all()


@router.post("/requisitos", response_model=schemas.RequisitoOut, status_code=201)
def crear_requisito(data: schemas.RequisitoUpsert, db: Session = Depends(get_db)):
    r = models.Requisito(**data.model_dump())
    db.add(r); db.commit(); db.refresh(r)
    return r


# ---------------- Gasistas / Institutos ----------------
@router.get("/gasistas", response_model=list[schemas.GasistaOut])
def gasistas(db: Session = Depends(get_db)):
    return db.scalars(select(models.Gasista).order_by(models.Gasista.nombre)).all()


@router.post("/gasistas", response_model=schemas.GasistaOut, status_code=201)
def crear_gasista(data: schemas.GasistaUpsert, db: Session = Depends(get_db)):
    g = models.Gasista(**data.model_dump())
    db.add(g); db.commit(); db.refresh(g)
    return g


# ---------------- Montos máximos por período ----------------
@router.get("/montos-periodo", response_model=list[schemas.MontoPeriodoOut])
def montos_periodo(db: Session = Depends(get_db)):
    return db.scalars(select(models.MontoPeriodo).order_by(
        models.MontoPeriodo.periodo.desc())).all()


@router.post("/montos-periodo", response_model=schemas.MontoPeriodoOut, status_code=201)
def crear_monto_periodo(data: schemas.MontoPeriodoUpsert, db: Session = Depends(get_db)):
    m = models.MontoPeriodo(**data.model_dump())
    db.add(m); db.commit(); db.refresh(m)
    return m
