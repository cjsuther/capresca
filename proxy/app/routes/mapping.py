"""
Mapeo de rutas del gateway a microservicios y permisos requeridos.
"""
import re
from app.config import settings

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
