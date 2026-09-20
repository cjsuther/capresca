"""Módulo Clientes/Agentes (VFP: maeclientes)."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.codigos import codigo_cliente, codigo_cliente_provisorio
from app.core.database import get_db
from app.core.idempotency import con_idempotencia
from app.core.pagination import paginar
from app.core.permisos import requiere_permiso
from app.deps import get_current_user
from app.domain.margen import valida_cuil
from app import models, schemas

router = APIRouter(prefix="/api/creditos/clientes", tags=["clientes"],
                   dependencies=[Depends(get_current_user)])

# H-156: enforcement RBAC fino por pantalla en el BACKEND (no sólo en el front). Las ESCRITURAS del maestro
# exigen nivel ESCRITURA sobre "/clientes/maestro". Lectura queda permisiva (la usa la búsqueda de cliente de
# varios circuitos); ADMG y los roles sin RBAC configurado siguen pasando (sin_restricciones → TOTAL).
_req_escritura_cliente = requiere_permiso("/clientes/maestro", "ESCRITURA")

# Largos máximos de las columnas String de Cliente (para truncar y no romper).
from sqlalchemy import String as _String
_LARGOS = {c.name: c.type.length for c in models.Cliente.__table__.columns
           if isinstance(c.type, _String) and c.type.length}


def _truncar(datos: dict) -> dict:
    """Trunca cada string al largo de su columna (evita errores de longitud)."""
    return {k: (v[:_LARGOS[k]] if isinstance(v, str) and k in _LARGOS else v)
            for k, v in datos.items()}


@router.get("", response_model=schemas.Pagina[schemas.ClienteOut])
def listar(
    q: str | None = Query(None, description="Busca por CUIL, DNI o apellido/nombre"),
    estado: str = Query("activos", description="activos | baja | todos"),
    organismo_id: int | None = None,
    limit: int = Query(25, le=200),
    offset: int = 0,
    sort: str = "apellido_nombre",
    order: str = "asc",
    db: Session = Depends(get_db),
):
    base = select(models.Cliente)
    if q:
        like = f"%{q.upper()}%"
        base = base.where(or_(
            models.Cliente.cuil.like(like),
            models.Cliente.dni.like(like),
            models.Cliente.apellido_nombre.like(like),
        ))
    if estado == "activos":
        base = base.where(models.Cliente.baja.is_(False))
    elif estado == "baja":
        base = base.where(models.Cliente.baja.is_(True))
    if organismo_id:
        base = base.where(models.Cliente.organismo_id == organismo_id)
    columnas = {"apellido_nombre": models.Cliente.apellido_nombre,
                "cuil": models.Cliente.cuil, "sueldo": models.Cliente.sueldo,
                "id_cliente": models.Cliente.id_cliente}
    return paginar(db, base, model=models.Cliente, columnas=columnas,
                   limit=limit, offset=offset, sort=sort, order=order)


@router.get("/{cliente_id}", response_model=schemas.ClienteOut)
def obtener(cliente_id: int, db: Session = Depends(get_db)):
    c = db.get(models.Cliente, cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return c


@router.post("", response_model=schemas.ClienteOut, status_code=201)
def crear(data: schemas.ClienteCreate, db: Session = Depends(get_db),
          idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
          _perm: models.Usuario = Depends(_req_escritura_cliente)):
    if not valida_cuil(data.cuil):
        raise HTTPException(422, "CUIL inválido (dígito verificador)")

    def _do():
        # Chequeo amistoso (mensaje claro) + inserción con la CONSTRAINT como árbitro real (H-154): dos
        # altas concurrentes con el mismo CUIL no pueden crear un duplicado; la 2ª cae en IntegrityError → 409.
        if db.query(models.Cliente).filter_by(cuil=data.cuil).first():
            raise HTTPException(409, "Ya existe un cliente con ese CUIL")
        datos = _truncar(data.model_dump())
        # H-169: el id_cliente NO es el CUIL ni un N° de solicitud: se AUTOGENERA del PK (surrogate).
        # Sólo se respeta uno explícito si viene de la migración/ETL (código legacy CIDCLIENTE).
        manual = (datos.get("id_cliente") or "").strip()
        datos["id_cliente"] = manual or codigo_cliente_provisorio()
        c = models.Cliente(**datos)
        db.add(c)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            if db.query(models.Cliente).filter_by(cuil=data.cuil).first():
                raise HTTPException(409, "Ya existe un cliente con ese CUIL")
            raise HTTPException(409, "Ya existe un cliente con ese código (id_cliente)")
        if not manual:
            c.id_cliente = codigo_cliente(c.id)   # CL-000123 a partir del PK ya asignado
            db.flush()
        db.commit()
        return {"id": c.id}

    res = con_idempotencia(db, idempotency_key, "POST /api/clientes", _do)
    return db.get(models.Cliente, res["id"])


@router.put("/{cliente_id}", response_model=schemas.ClienteOut)
def modificar(cliente_id: int, data: schemas.ClienteUpdate, db: Session = Depends(get_db),
              _perm: models.Usuario = Depends(_req_escritura_cliente)):
    c = db.get(models.Cliente, cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    for campo, valor in _truncar(data.model_dump(exclude_unset=True)).items():
        setattr(c, campo, valor)
    db.commit()
    db.refresh(c)
    return c


@router.post("/{cliente_id}/baja", response_model=schemas.ClienteOut)
def dar_baja(cliente_id: int, data: schemas.ClienteBaja, db: Session = Depends(get_db),
             _perm: models.Usuario = Depends(_req_escritura_cliente)):
    from datetime import date as _date
    c = db.get(models.Cliente, cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    if not data.motivo.strip():
        raise HTTPException(422, "Indicá el motivo de la baja")
    c.baja = True
    c.fecha_baja = _date.today()
    c.motivo_baja = data.motivo.strip()[:200]
    db.commit()
    db.refresh(c)
    return c


@router.post("/{cliente_id}/reactivar", response_model=schemas.ClienteOut)
def reactivar(cliente_id: int, db: Session = Depends(get_db),
              _perm: models.Usuario = Depends(_req_escritura_cliente)):
    c = db.get(models.Cliente, cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    c.baja = False
    c.fecha_baja = None
    c.motivo_baja = ""
    db.commit()
    db.refresh(c)
    return c
