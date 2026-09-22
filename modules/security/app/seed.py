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
from app.models.permission import Permission, UserPermission
from app.models.role import Role
from app.models.user import User
from app.services.auth_service import hash_password

MODULES = [
    {"code": "security", "name": "Seguridad", "description": "Gestión de usuarios, roles y permisos", "icon": "shield"},
    {"code": "cajeros", "name": "Cajeros", "description": "Solicitudes y autorizaciones de operaciones", "icon": "banknotes"},
    {"code": "clientes", "name": "Clientes", "description": "Gestión de clientes y contactos", "icon": "users"},
    {"code": "interbanking", "name": "Interbanking", "description": "Operaciones bancarias via Interbanking Argentina", "icon": "banknote"},
    {"code": "conciliacion", "name": "Conciliación", "description": "Conciliación de pagos y transferencias", "icon": "scale"},
    {"code": "liquidaciones", "name": "Liquidaciones", "description": "Procesamiento de liquidaciones de juegos", "icon": "receipt"},
    {"code": "comunicacion", "name": "Comunicación", "description": "Chat con clientes vía WhatsApp Business", "icon": "message-circle"},
    {"code": "legacy", "name": "Legacy", "description": "Integración con el sistema legacy (VFP9) — interacciones IN/OUT", "icon": "database"},
    {"code": "creditos", "name": "Créditos", "description": "CCyPP: créditos, originación, cartera y portal ciudadano", "icon": "landmark"},
    {"code": "tesoreria", "name": "Tesorería", "description": "Lotes de pagos: aprobación y envío por Interbanking", "icon": "wallet"},
    {"code": "configuraciones", "name": "Configuraciones", "description": "Impuestos, índices, feriados y workflow de aprobaciones", "icon": "settings"},
]

# Créditos: permisos por área (<area>:read / <area>:write). Debe coincidir con
# modules/creditos/backend/app/core/gateway.py y con proxy/app/routes/mapping.py.
CREDITOS_AREAS = [
    ("creditos", "créditos"),
]

# Áreas de CCyPP que no se migraron a Portezuelo: sus permisos se retiran de la base (y de los roles y
# usuarios que los tuvieran) para que no aparezcan en Seguridad habilitando pantallas que no existen.
CREDITOS_AREAS_RETIRADAS = ("clientes", "caja", "tesoreria", "contabilidad", "seguros", "despacho",
                            "mesa", "juegos", "general", "seguridad")

PERMISSIONS = {
    "security": [
        ("users:read", "Ver usuarios"),
        ("users:write", "Crear/editar usuarios"),
        ("roles:read", "Ver roles"),
        ("roles:write", "Crear/editar roles"),
        ("groups:read", "Ver grupos de usuarios"),
        ("groups:write", "Crear/editar grupos, sus integrantes y sus roles"),
        ("modules:read", "Ver módulos"),
    ],
    "cajeros": [
        ("rules:read", "Ver reglas de autorización"),
        ("rules:write", "Crear/eliminar reglas de autorización"),
        ("transactions:read", "Ver transacciones propias"),
        ("transactions:read_all", "Ver todas las transacciones"),
        ("transactions:write", "Registrar transacciones"),
        ("transactions:authorize", "Autorizar o rechazar transacciones"),
        ("transactions:delete", "Eliminar transacciones propias"),
        ("transactions:admin", "Administrar todas las transacciones"),
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
    "conciliacion": [
        ("read", "Ver conciliación"),
        ("write", "Editar conciliación y gestionar vínculos"),
        ("download", "Descargar boletas PDF"),
    ],
    "liquidaciones": [
        ("liq:read", "Ver liquidaciones y lotes"),
        ("liq:write", "Procesar archivos y enviar a conciliación"),
        ("liq:download", "Descargar archivos adjuntos"),
    ],
    "comunicacion": [
        ("chat:read", "Ver conversaciones y mensajes"),
        ("chat:write", "Enviar mensajes y crear conversaciones"),
        ("chat:config:read", "Ver configuración del menú y WhatsApp"),
        ("chat:config:write", "Modificar configuración del menú y WhatsApp"),
    ],
    "legacy": [
        ("interactions:read", "Ver interacciones y estado de la integración legacy"),
        ("admin:read", "Ver outbox de escrituras"),
        ("admin:write", "Forzar sync y drenar el outbox"),
    ],
    # Tesorería: armar/revisar lotes, enviarlos al banco y aprobar (roles del workflow LOTE_PAGO).
    "tesoreria": [
        ("lotes:read", "Tesorería · ver lotes de pagos"),
        ("lotes:write", "Tesorería · cargar lotes y excluir pagos"),
        ("lotes:enviar", "Tesorería · enviar lotes aprobados por Interbanking"),
        ("aprobaciones:aprobar", "Tesorería · aprobar lotes (rol APROBAR del workflow)"),
        ("aprobaciones:supervisar", "Tesorería · aprobar niveles de supervisión (rol SUPERVISAR)"),
    ],
    # Un par por catálogo: el workflow (quién aprueba) se asigna aparte de operar los módulos.
    "configuraciones": [
        ("impuestos:read", "Configuraciones · ver impuestos"),
        ("impuestos:write", "Configuraciones · editar impuestos"),
        ("indices:read", "Configuraciones · ver índices de referencia"),
        ("indices:write", "Configuraciones · editar índices de referencia"),
        ("feriados:read", "Configuraciones · ver el calendario de feriados"),
        ("feriados:write", "Configuraciones · editar el calendario de feriados"),
        ("workflow:read", "Configuraciones · ver el workflow de aprobaciones"),
        ("workflow:write", "Configuraciones · configurar el workflow de aprobaciones"),
    ],
    "creditos": [
        *[perm for area, label in CREDITOS_AREAS for perm in (
            (f"{area}:read", f"Créditos · ver {label}"),
            (f"{area}:write", f"Créditos · operar {label}"),
        )],
        ("aprobaciones:aprobar", "Créditos · aprobar (workflow, rol APROBAR)"),
        ("aprobaciones:supervisar", "Créditos · aprobar niveles de supervisión (workflow, rol SUPERVISAR)"),
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
        # Clave (módulo, código): el código ya no es único global, así que dos módulos pueden
        # declarar el mismo (p.ej. `caja:read`) sin pisarse.
        perm_map: dict[tuple[str, str], Permission] = {}
        for module_code, perms in PERMISSIONS.items():
            mod = module_map[module_code]
            for code, desc in perms:
                existing = db.query(Permission).filter(
                    Permission.module_id == mod.id, Permission.code == code
                ).first()
                if not existing:
                    obj = Permission(module_id=mod.id, code=code, description=desc)
                    db.add(obj)
                    db.flush()
                    perm_map[(module_code, code)] = obj
                else:
                    perm_map[(module_code, code)] = existing

        # ── Permisos retirados ───────────────────────────────────
        retirados = [f"{area}:{accion}" for area in CREDITOS_AREAS_RETIRADAS for accion in ("read", "write")]
        obsoletos = db.query(Permission).filter(
            Permission.module_id == module_map["creditos"].id, Permission.code.in_(retirados)).all()
        for perm in obsoletos:
            db.query(UserPermission).filter(UserPermission.permission_id == perm.id).delete()
            db.delete(perm)   # la relación con roles es `secondary`: se borra la fila de role_permissions
        db.flush()

        # ── Rol admin ────────────────────────────────────────────
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            admin_role = Role(name="admin", description="Administrador del sistema")
            db.add(admin_role)
            db.flush()
            admin_role.permissions = list(perm_map.values())
        else:
            # Solo agregar permisos nuevos sin quitar los existentes
            existing_ids = {p.id for p in admin_role.permissions}
            for perm in perm_map.values():
                if perm.id not in existing_ids:
                    admin_role.permissions.append(perm)

        # ── Rol cajero ───────────────────────────────────────────
        cajero_role = db.query(Role).filter(Role.name == "cajero").first()
        if not cajero_role:
            cajero_role = Role(name="cajero", description="Cajero estándar")
            db.add(cajero_role)
            db.flush()
            cajero_perms = [p for (_mod, code), p in perm_map.items() if code in (
                "transactions:read", "transactions:write", "transactions:delete",
                "clients:read",
            )]
            cajero_role.permissions = cajero_perms

        # ── Rol supervisor ───────────────────────────────────────
        supervisor_role = db.query(Role).filter(Role.name == "supervisor").first()
        if not supervisor_role:
            supervisor_role = Role(name="supervisor", description="Supervisor / Autorizador")
            db.add(supervisor_role)
            db.flush()
            supervisor_perms = [p for (_mod, code), p in perm_map.items() if code in (
                "transactions:read", "transactions:read_all", "transactions:authorize",
                "rules:read", "rules:write",
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
