from collections import defaultdict
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.permission import Permission, UserPermission
from app.models.module import Module


def get_user_permissions(db: Session, user_id: int) -> dict:
    """
    Calcula los permisos efectivos de un usuario combinando:
    - Permisos heredados por roles
    - Permisos directos (overrides: granted=True/False)

    Retorna: { "modules": [...], "actions": { "module_code": [...] } }
    """
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        return {"modules": [], "actions": {}}

    # Permisos por roles
    role_perm_ids: set[int] = set()
    for role in user.roles:
        if not role.is_active:
            continue
        for perm in role.permissions:
            role_perm_ids.add(perm.id)

    # Overrides directos
    denied: set[int] = set()
    granted_extra: set[int] = set()
    for up in user.direct_permissions:
        if up.granted:
            granted_extra.add(up.permission_id)
        else:
            denied.add(up.permission_id)

    effective_ids = (role_perm_ids | granted_extra) - denied

    if not effective_ids:
        return {"modules": [], "actions": {}}

    perms = (
        db.query(Permission)
        .filter(Permission.id.in_(effective_ids))
        .join(Module)
        .filter(Module.is_active == True)
        .all()
    )

    modules_set: set[str] = set()
    actions: dict[str, list[str]] = defaultdict(list)

    for perm in perms:
        module_code = perm.module.code
        modules_set.add(module_code)
        # code es como "requests:read" — lo guardamos tal cual bajo el módulo
        actions[module_code].append(perm.code)

    return {
        "modules": sorted(modules_set),
        "actions": dict(actions),
    }


def get_user_modules(db: Session, user_id: int) -> list[str]:
    data = get_user_permissions(db, user_id)
    return data["modules"]
