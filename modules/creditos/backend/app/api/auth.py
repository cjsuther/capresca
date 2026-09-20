"""Sesión del backoffice. El login lo hace Portezuelo; acá sólo se exponen los permisos efectivos."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.deps import get_current_user
from app import models

router = APIRouter(prefix="/api/creditos/auth", tags=["auth"])


@router.get("/mis-permisos")
def mis_permisos(db: Session = Depends(get_db), user: models.Usuario = Depends(get_current_user)):
    """Permisos efectivos del usuario, para gatear menú/pantallas/acciones en el front.
    `areas` = { área: CONSULTA|ESCRITURA }; `roles` = roles de aprobación del workflow."""
    from app.core.permisos import roles_de, permisos_efectivos
    roles = sorted(roles_de(db, user))
    return {"usuario": user.username, "nombre": user.nombre, "roles": roles,
            "sinRestricciones": False, "areas": permisos_efectivos(db, user)}
