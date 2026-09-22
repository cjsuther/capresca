"""
Clientes en Créditos: ESPEJO del padrón de Portezuelo (módulo Clientes).

El alta, la edición y la baja de una persona se hacen en el módulo Clientes: acá sólo se lee el
espejo (para las grillas y los reportes de créditos) y se sincroniza contra el padrón. Lo propio
del crédito —sueldo, organismo, categoría, débito automático— se edita en la ficha crediticia.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core import clientes_padron
from app.core.database import get_db
from app.core.pagination import paginar
from app.core.permisos import requiere_permiso
from app.deps import get_current_user
from app import models, schemas

router = APIRouter(prefix="/api/creditos/clientes", tags=["clientes"],
                   dependencies=[Depends(get_current_user)])

# H-156/H-205: el nivel se enforca también en el BACKEND (defensa en profundidad detrás del gateway).
# Sincronizar el espejo y editar el perfil crediticio exigen ESCRITURA sobre el área Créditos: el maestro
# de personas ya no se administra acá, así que no hay un área "clientes" propia.
_req_escritura_cliente = requiere_permiso("/creditos/clientes", "ESCRITURA")

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
    # Si todavía no está espejado (cliente nuevo del padrón), se trae en el momento.
    c = clientes_padron.obtener(db, cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    return c


@router.post("/{cliente_id}/sincronizar", response_model=schemas.ClienteOut)
def sincronizar(cliente_id: int, db: Session = Depends(get_db),
                _perm: models.Usuario = Depends(_req_escritura_cliente)):
    """Refresca el espejo con la identidad que tiene hoy el padrón."""
    c = clientes_padron.sincronizar(db, cliente_id)
    if not c:
        raise HTTPException(404, "El cliente no existe en el padrón de Portezuelo")
    return c


@router.put("/{cliente_id}/perfil-crediticio", response_model=schemas.ClienteOut)
def editar_perfil_crediticio(cliente_id: int, data: schemas.ClientePerfilCrediticio,
                             db: Session = Depends(get_db),
                             _perm: models.Usuario = Depends(_req_escritura_cliente)):
    """
    Datos que sí son de Créditos: sueldo, organismo, categoría, débito automático. La identidad
    (nombre, documento, domicilio, contacto) se edita en el módulo Clientes.
    """
    c = clientes_padron.obtener(db, cliente_id)
    if not c:
        raise HTTPException(404, "Cliente no encontrado")
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(c, campo, valor)
    db.commit()
    db.refresh(c)
    return c
