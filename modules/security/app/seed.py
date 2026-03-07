"""
Seed de datos iniciales:
  - Módulos del sistema
  - Permisos atómicos por módulo
  - Rol admin (todos los permisos)
  - Usuario admin inicial
"""
import sys
from app.db.session import SessionLocal
from app.models.module import Module
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import hash_password

MODULES = [
    {"code": "security", "name": "Seguridad", "description": "Gestión de usuarios, roles y permisos", "icon": "shield"},
    {"code": "cajeros", "name": "Cajeros", "description": "Solicitudes y autorizaciones de operaciones", "icon": "banknotes"},
    {"code": "clientes", "name": "Clientes", "description": "Gestión de clientes y contactos", "icon": "users"},
    {"code": "interbanking", "name": "Interbanking", "description": "Operaciones bancarias via Interbanking Argentina", "icon": "banknote"},
]

PERMISSIONS = {
    "security": [
        ("users:read", "Ver usuarios"),
        ("users:write", "Crear/editar usuarios"),
        ("roles:read", "Ver roles"),
        ("roles:write", "Crear/editar roles"),
        ("modules:read", "Ver módulos"),
    ],
    "cajeros": [
        ("requests:read", "Ver solicitudes"),
        ("requests:write", "Crear solicitudes"),
        ("requests:authorize", "Autorizar/rechazar solicitudes"),
        ("limits:read", "Ver límites"),
        ("limits:write", "Editar límites"),
        ("relations:read", "Ver relaciones cajero-autorizador"),
        ("relations:write", "Gestionar relaciones"),
        ("operations:read", "Ver historial de operaciones"),
    ],
    "clientes": [
        ("clients:read", "Ver clientes"),
        ("clients:write", "Crear/editar clientes"),
        ("contacts:read", "Ver contactos"),
        ("contacts:write", "Gestionar contactos"),
        ("notes:read", "Ver notas"),
        ("notes:write", "Agregar notas"),
    ],
    "interbanking": [
        ("config:read", "Ver configuración de credenciales"),
        ("config:write", "Crear/editar credenciales"),
        ("cuentas:read", "Consultar cuentas y saldos"),
        ("transferencias:read", "Ver historial de transferencias"),
        ("transferencias:write", "Iniciar transferencias y validar CBU"),
        ("pagos:read", "Ver lotes de pago"),
        ("pagos:write", "Crear y procesar lotes"),
        ("auditoria:read", "Ver log de auditoría"),
    ],
}


def run():
    db = SessionLocal()
    try:
        # ── Módulos ──────────────────────────────────────────────
        module_map: dict[str, Module] = {}
        for m in MODULES:
            existing = db.query(Module).filter(Module.code == m["code"]).first()
            if not existing:
                obj = Module(**m)
                db.add(obj)
                db.flush()
                module_map[m["code"]] = obj
            else:
                module_map[m["code"]] = existing

        # ── Permisos ─────────────────────────────────────────────
        perm_map: dict[str, Permission] = {}
        for module_code, perms in PERMISSIONS.items():
            mod = module_map[module_code]
            for code, desc in perms:
                existing = db.query(Permission).filter(Permission.code == code).first()
                if not existing:
                    obj = Permission(module_id=mod.id, code=code, description=desc)
                    db.add(obj)
                    db.flush()
                    perm_map[code] = obj
                else:
                    perm_map[code] = existing

        # ── Rol admin ────────────────────────────────────────────
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin", description="Administrador del sistema")
            db.add(admin_role)
            db.flush()

        admin_role.permissions = list(perm_map.values())

        # ── Rol cajero ───────────────────────────────────────────
        cajero_role = db.query(Role).filter(Role.name == "cajero").first()
        if not cajero_role:
            cajero_role = Role(name="cajero", description="Cajero estándar")
            db.add(cajero_role)
            db.flush()

        cajero_perms = [p for code, p in perm_map.items() if code in (
            "cajeros:requests:read", "cajeros:requests:write",
            "cajeros:limits:read", "cajeros:operations:read",
            "clientes:clients:read",
        )]
        # Usar códigos sin prefijo de módulo (como están guardados)
        cajero_perms = [p for code, p in perm_map.items() if code in (
            "requests:read", "requests:write",
            "limits:read", "operations:read",
            "clients:read",
        )]
        cajero_role.permissions = cajero_perms

        # ── Rol supervisor ───────────────────────────────────────
        supervisor_role = db.query(Role).filter(Role.name == "supervisor").first()
        if not supervisor_role:
            supervisor_role = Role(name="supervisor", description="Supervisor / Autorizador")
            db.add(supervisor_role)
            db.flush()

        supervisor_perms = [p for code, p in perm_map.items() if code in (
            "requests:read", "requests:authorize",
            "limits:read", "limits:write",
            "relations:read", "relations:write",
            "operations:read",
            "clients:read",
        )]
        supervisor_role.permissions = supervisor_perms

        # ── Usuario admin ────────────────────────────────────────
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                email="admin@sistema.local",
                hashed_password=hash_password("Admin1234!"),
                full_name="Administrador del Sistema",
                is_active=True,
            )
            db.add(admin_user)
            db.flush()

        if admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)

        db.commit()
        print("[seed] Datos iniciales cargados correctamente.")
    except Exception as e:
        db.rollback()
        print(f"[seed] Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    run()
