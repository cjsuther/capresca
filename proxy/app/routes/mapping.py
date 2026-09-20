"""
Mapeo de rutas del gateway a microservicios y permisos requeridos.
"""
import re
from app.config import settings


def _creditos_area(path_regex: str, area: str) -> list:
    return [
        ("GET", path_regex, settings.creditos_service_url, f"creditos:{area}:read"),
        (None,  path_regex, settings.creditos_service_url, f"creditos:{area}:write"),
    ]


def _creditos_rutas() -> list:
    url = settings.creditos_service_url
    base = r"^/api/creditos"
    catalogos_general = r"(lineas|organismos|proveedores|companias|parametros|requisitos|gasistas|montos-periodo)"
    return [
        ("GET",  base + r"/auth/mis-permisos$",                            url, "creditos:*"),
        # Aprobaciones: el módulo exige el rol de aprobación que pide cada nivel del workflow.
        ("GET",  base + r"/aprobaciones/(inbox|count)$",                   url, "creditos:*"),
        ("POST", base + r"/aprobaciones/pendientes/[^/]+/(aprobar|rechazar)$", url, "creditos:*"),
        # Cambios de estado: mezclan acciones de edición y de aprobación; el módulo las gatea por acción.
        ("POST", base + r"/productos/[^/]+/estado$",                       url, "creditos:*"),
        ("POST", base + r"/solicitudes/[^/]+/estado$",                     url, "creditos:*"),
        # Catálogos compartidos: los lee cualquier pantalla del módulo; se editan desde su área.
        ("GET",  base + r"/(impuestos|indices|feriados)(/|$)",             url, "creditos:*"),
        ("GET",  base + r"/admin/" + catalogos_general + r"(/|$)",         url, "creditos:*"),
        *_creditos_area(base + r"/(impuestos|indices|feriados)(/|$)",      "contabilidad"),
        *_creditos_area(base + r"/admin/" + catalogos_general + r"(/|$)",  "general"),
        # Seguridad del módulo: auditoría y workflow.
        *_creditos_area(base + r"/admin/(auditoria|auditoria-cambios)(/|$)", "seguridad"),
        *_creditos_area(base + r"/(workflow|controles-version|migradores)(/|$)", "seguridad"),
        # Áreas funcionales.
        *_creditos_area(base + r"/(creditos|solicitudes|productos|contratos|sistema-calculos)(/|$)", "creditos"),
        *_creditos_area(base + r"/clientes(/|$)",     "clientes"),
        *_creditos_area(base + r"/caja(/|$)",         "caja"),
        *_creditos_area(base + r"/egresos(/|$)",      "tesoreria"),
        *_creditos_area(base + r"/contabilidad(/|$)", "contabilidad"),
        *_creditos_area(base + r"/seguros(/|$)",      "seguros"),
        *_creditos_area(base + r"/despacho(/|$)",     "despacho"),
        *_creditos_area(base + r"/mesa(/|$)",         "mesa"),
        *_creditos_area(base + r"/juegos(/|$)",       "juegos"),
    ]


# (method, pattern_regex) → (service_base_url, required_permission | None)
ROUTE_MAP = [
    # ── Auth (sin permiso requerido) ────────────────────────────
    (None,   r"^/api/auth/",                settings.security_service_url, None),

    # ── Security ────────────────────────────────────────────────
    ("GET",  r"^/api/security/users",       settings.security_service_url, "security:users:read"),
    ("PUT",  r"^/api/security/users/me/password$",    settings.security_service_url, None),
    ("PUT",  r"^/api/security/users/\d+/password$",  settings.security_service_url, "security:users:write"),
    ("POST", r"^/api/security/users/\d+/roles$",     settings.security_service_url, "security:users:write"),
    ("POST", r"^/api/security/users$",               settings.security_service_url, "security:users:write"),
    ("PUT",  r"^/api/security/users/",               settings.security_service_url, "security:users:write"),
    ("DELETE", r"^/api/security/users/",             settings.security_service_url, "security:users:write"),
    ("GET",    r"^/api/security/roles",         settings.security_service_url, "security:roles:read"),
    ("POST",   r"^/api/security/roles/\d+/permissions$", settings.security_service_url, "security:roles:write"),
    ("POST",   r"^/api/security/roles$",               settings.security_service_url, "security:roles:write"),
    ("PUT",    r"^/api/security/roles/",        settings.security_service_url, "security:roles:write"),
    ("DELETE", r"^/api/security/roles/",        settings.security_service_url, "security:roles:write"),
    ("GET",    r"^/api/security/permissions",   settings.security_service_url, "security:roles:read"),
    ("GET",    r"^/api/security/modules",       settings.security_service_url, "security:modules:read"),

    # ── Cajeros ─────────────────────────────────────────────────
    ("GET",    r"^/api/cajeros/rules$",                          settings.cajeros_service_url, "cajeros:rules:read"),
    ("POST",   r"^/api/cajeros/rules$",                          settings.cajeros_service_url, "cajeros:rules:write"),
    ("DELETE", r"^/api/cajeros/rules/\d+$",                      settings.cajeros_service_url, "cajeros:rules:write"),
    ("POST",   r"^/api/cajeros/transactions$",                   settings.cajeros_service_url, "cajeros:transactions:write"),
    ("GET",    r"^/api/cajeros/transactions$",                   settings.cajeros_service_url, "cajeros:transactions:read"),
    ("GET",    r"^/api/cajeros/transactions/\d+$",               settings.cajeros_service_url, "cajeros:transactions:read"),
    ("PUT",    r"^/api/cajeros/transactions/\d+/authorize$",     settings.cajeros_service_url, "cajeros:transactions:authorize"),
    ("PUT",    r"^/api/cajeros/transactions/\d+/reject$",        settings.cajeros_service_url, "cajeros:transactions:authorize"),
    ("DELETE", r"^/api/cajeros/transactions/\d+$",               settings.cajeros_service_url, "cajeros:transactions:delete"),

    # ── Notifications ────────────────────────────────────────────
    ("GET",  r"^/api/notifications/unread-count$",   settings.notifications_service_url, None),
    ("PUT",  r"^/api/notifications/read-all$",       settings.notifications_service_url, None),
    ("PUT",  r"^/api/notifications/\d+/read$",       settings.notifications_service_url, None),
    ("GET",  r"^/api/notifications",                 settings.notifications_service_url, None),

    # ── Clientes ────────────────────────────────────────────────
    ("GET",    r"^/api/clientes/\d+/cbus$",         settings.clientes_service_url, "clientes:clients:read"),
    ("POST",   r"^/api/clientes/\d+/cbus$",         settings.clientes_service_url, "clientes:clients:write"),
    ("PUT",    r"^/api/clientes/\d+/cbus/\d+$",     settings.clientes_service_url, "clientes:clients:write"),
    ("DELETE", r"^/api/clientes/\d+/cbus/\d+$",     settings.clientes_service_url, "clientes:clients:write"),
    ("GET",    r"^/api/clientes",                   settings.clientes_service_url, "clientes:clients:read"),
    ("POST",   r"^/api/clientes/human$",            settings.clientes_service_url, "clientes:clients:write"),
    ("POST",   r"^/api/clientes/legal$",            settings.clientes_service_url, "clientes:clients:write"),
    ("PUT",    r"^/api/clientes/\d+/human$",        settings.clientes_service_url, "clientes:clients:write"),
    ("PUT",    r"^/api/clientes/\d+/legal$",        settings.clientes_service_url, "clientes:clients:write"),
    ("PUT",    r"^/api/clientes/",                  settings.clientes_service_url, "clientes:clients:write"),
    ("DELETE", r"^/api/clientes/\d+/members/\d+$", settings.clientes_service_url, "clientes:clients:write"),
    ("DELETE", r"^/api/clientes/",                  settings.clientes_service_url, "clientes:clients:write"),
    ("POST",   r"^/api/clientes/\d+/contacts",      settings.clientes_service_url, "clientes:contacts:write"),
    ("DELETE", r"^/api/clientes/\d+/contacts/",     settings.clientes_service_url, "clientes:contacts:write"),
    ("POST",   r"^/api/clientes/\d+/notes",         settings.clientes_service_url, "clientes:notes:write"),
    ("GET",    r"^/api/clientes/\d+/members",       settings.clientes_service_url, "clientes:clients:read"),
    ("POST",   r"^/api/clientes/\d+/members",       settings.clientes_service_url, "clientes:clients:write"),

    # ── Conciliación ─────────────────────────────────────────────
    ("GET",  r"^/api/conciliacion/records/\d+/boleta$",              settings.conciliacion_service_url, "conciliacion:download"),
    ("GET",  r"^/api/conciliacion/records/\d+/history$",             settings.conciliacion_service_url, "conciliacion:read"),
    ("GET",  r"^/api/conciliacion/records/\d+/adjustments$",         settings.conciliacion_service_url, "conciliacion:read"),
    ("POST", r"^/api/conciliacion/records/\d+/adjustments$",         settings.conciliacion_service_url, "conciliacion:write"),
    ("GET",  r"^/api/conciliacion/records/\d+$",                     settings.conciliacion_service_url, "conciliacion:read"),
    ("PUT",  r"^/api/conciliacion/records/\d+$",                     settings.conciliacion_service_url, "conciliacion:write"),
    ("PUT",  r"^/api/conciliacion/interbanking/\w+/\d+/agency$",     settings.conciliacion_service_url, "conciliacion:write"),
    ("DELETE", r"^/api/conciliacion/links/\d+$",                     settings.conciliacion_service_url, "conciliacion:write"),
    ("GET",  r"^/api/conciliacion/summary$",                         settings.conciliacion_service_url, "conciliacion:read"),
    ("GET",  r"^/api/conciliacion/agencies$",                        settings.conciliacion_service_url, "conciliacion:read"),
    ("GET",  r"^/api/conciliacion$",                                 settings.conciliacion_service_url, "conciliacion:read"),

    # ── Liquidaciones ────────────────────────────────────────────
    ("POST", r"^/api/liquidaciones/process$",                              settings.liquidaciones_service_url, "liquidaciones:liq:write"),
    ("POST", r"^/api/liquidaciones/upload$",                               settings.liquidaciones_service_url, "liquidaciones:liq:write"),
    ("GET",  r"^/api/liquidaciones/batches/\d+/detalle$",                  settings.liquidaciones_service_url, "liquidaciones:liq:read"),
    ("GET",  r"^/api/liquidaciones/batches/\d+/validaciones$",             settings.liquidaciones_service_url, "liquidaciones:liq:read"),
    ("GET",  r"^/api/liquidaciones/batches/\d+/archivos/\d+$",             settings.liquidaciones_service_url, "liquidaciones:liq:download"),
    ("GET",  r"^/api/liquidaciones/batches/\d+/archivos$",                 settings.liquidaciones_service_url, "liquidaciones:liq:read"),
    ("GET",  r"^/api/liquidaciones/batches/\d+/raw$",                      settings.liquidaciones_service_url, "liquidaciones:liq:read"),
    ("POST", r"^/api/liquidaciones/batches/\d+/retry-conciliacion$",       settings.liquidaciones_service_url, "liquidaciones:liq:write"),
    ("GET",  r"^/api/liquidaciones/batches/\d+$",                          settings.liquidaciones_service_url, "liquidaciones:liq:read"),
    ("GET",  r"^/api/liquidaciones/batches$",                              settings.liquidaciones_service_url, "liquidaciones:liq:read"),


    # ── Interbanking ─────────────────────────────────────────────
    ("GET",    r"^/api/interbanking/config/token-status$",          settings.interbanking_service_url, "interbanking:config:read"),
    ("POST",   r"^/api/interbanking/config/test$",                  settings.interbanking_service_url, "interbanking:config:write"),
    ("GET",    r"^/api/interbanking/config$",                       settings.interbanking_service_url, "interbanking:config:read"),
    ("POST",   r"^/api/interbanking/config$",                       settings.interbanking_service_url, "interbanking:config:write"),
    ("GET",    r"^/api/interbanking/cuentas/saldos$",               settings.interbanking_service_url, "interbanking:cuentas:read"),
    ("GET",    r"^/api/interbanking/cuentas/[^/]+/movimientos$",     settings.interbanking_service_url, "interbanking:cuentas:read"),
    ("GET",    r"^/api/interbanking/cuentas",                       settings.interbanking_service_url, "interbanking:cuentas:read"),
    ("POST",   r"^/api/interbanking/transferencias/validar$",       settings.interbanking_service_url, "interbanking:transferencias:write"),
    ("GET",    r"^/api/interbanking/transferencias/local$",         settings.interbanking_service_url, "interbanking:transferencias:read"),
    ("GET",    r"^/api/interbanking/transferencias/\w+/estado$",    settings.interbanking_service_url, "interbanking:transferencias:read"),
    ("POST",   r"^/api/interbanking/transferencias$",               settings.interbanking_service_url, "interbanking:transferencias:write"),
    ("GET",    r"^/api/interbanking/transferencias",                settings.interbanking_service_url, "interbanking:transferencias:read"),
    ("GET",    r"^/api/interbanking/auditoria/export$",             settings.interbanking_service_url, "interbanking:auditoria:read"),
    ("GET",    r"^/api/interbanking/auditoria/\d+$",                settings.interbanking_service_url, "interbanking:auditoria:read"),
    ("GET",    r"^/api/interbanking/auditoria",                     settings.interbanking_service_url, "interbanking:auditoria:read"),

    # ── Legacy (solo administración/diagnóstico; los /internal nunca se exponen) ──
    ("GET",    r"^/api/legacy/interactions/\d+$",   settings.legacy_service_url, "legacy:interactions:read"),
    ("GET",    r"^/api/legacy/interactions$",       settings.legacy_service_url, "legacy:interactions:read"),
    ("GET",    r"^/api/legacy/databases$",          settings.legacy_service_url, "legacy:interactions:read"),
    ("GET",    r"^/api/legacy/status$",             settings.legacy_service_url, "legacy:interactions:read"),
    ("POST",   r"^/api/legacy/sync/\w+$",           settings.legacy_service_url, "legacy:admin:write"),
    ("GET",    r"^/api/legacy/outbox$",             settings.legacy_service_url, "legacy:admin:read"),
    ("POST",   r"^/api/legacy/outbox/drain$",       settings.legacy_service_url, "legacy:admin:write"),

    # ── Créditos (CCyPP) ─────────────────────────────────────────
    # Permisos por área: GET exige <area>:read y el resto de los métodos <area>:write.
    # "creditos:*" = cualquier permiso del módulo; lo usan las rutas cuya autorización fina
    # decide el módulo (aprobaciones, catálogos compartidos). El portal ciudadano NO pasa por
    # acá: nginx lo manda directo al módulo (realm propio). Las rutas no listadas dan 404.
    *_creditos_rutas(),
]


def get_service_url(method: str, path: str) -> str | None:
    for entry in ROUTE_MAP:
        m, pattern, service_url, _ = entry
        if (m is None or m == method) and re.match(pattern, path):
            return service_url
    return None


def get_required_permission(method: str, path: str) -> str | None:
    for entry in ROUTE_MAP:
        m, pattern, _, permission = entry
        if (m is None or m == method) and re.match(pattern, path):
            return permission
    return None
