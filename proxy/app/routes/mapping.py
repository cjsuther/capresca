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
    ("GET",  r"^/api/cajeros/limits",       settings.cajeros_service_url,  "cajeros:limits:read"),
    ("PUT",  r"^/api/cajeros/limits/",      settings.cajeros_service_url,  "cajeros:limits:write"),
    ("GET",  r"^/api/cajeros/relations",    settings.cajeros_service_url,  "cajeros:relations:read"),
    ("POST", r"^/api/cajeros/relations$",   settings.cajeros_service_url,  "cajeros:relations:write"),
    ("DELETE", r"^/api/cajeros/relations/", settings.cajeros_service_url,  "cajeros:relations:write"),
    ("POST", r"^/api/cajeros/requests$",    settings.cajeros_service_url,  "cajeros:requests:write"),
    ("GET",  r"^/api/cajeros/requests",     settings.cajeros_service_url,  "cajeros:requests:read"),
    ("PUT",  r"^/api/cajeros/requests/.+/approve$", settings.cajeros_service_url, "cajeros:requests:authorize"),
    ("PUT",  r"^/api/cajeros/requests/.+/reject$",  settings.cajeros_service_url, "cajeros:requests:authorize"),
    ("GET",  r"^/api/cajeros/operations",   settings.cajeros_service_url,  "cajeros:operations:read"),

    # ── Clientes ────────────────────────────────────────────────
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

    # ── Interbanking ─────────────────────────────────────────────
    ("GET",    r"^/api/interbanking/config/token-status$",          settings.interbanking_service_url, "interbanking:config:read"),
    ("POST",   r"^/api/interbanking/config/test$",                  settings.interbanking_service_url, "interbanking:config:write"),
    ("GET",    r"^/api/interbanking/config$",                       settings.interbanking_service_url, "interbanking:config:read"),
    ("POST",   r"^/api/interbanking/config$",                       settings.interbanking_service_url, "interbanking:config:write"),
    ("GET",    r"^/api/interbanking/cuentas/\w+/saldo$",            settings.interbanking_service_url, "interbanking:cuentas:read"),
    ("GET",    r"^/api/interbanking/cuentas",                       settings.interbanking_service_url, "interbanking:cuentas:read"),
    ("POST",   r"^/api/interbanking/transferencias/validar$",       settings.interbanking_service_url, "interbanking:transferencias:write"),
    ("POST",   r"^/api/interbanking/transferencias/iniciar$",       settings.interbanking_service_url, "interbanking:transferencias:write"),
    ("GET",    r"^/api/interbanking/transferencias/\w+/estado$",    settings.interbanking_service_url, "interbanking:transferencias:read"),
    ("GET",    r"^/api/interbanking/transferencias",                settings.interbanking_service_url, "interbanking:transferencias:read"),
    ("GET",    r"^/api/interbanking/auditoria/export$",             settings.interbanking_service_url, "interbanking:auditoria:read"),
    ("GET",    r"^/api/interbanking/auditoria/\d+$",                settings.interbanking_service_url, "interbanking:auditoria:read"),
    ("GET",    r"^/api/interbanking/auditoria",                     settings.interbanking_service_url, "interbanking:auditoria:read"),
    ("GET",    r"^/api/interbanking/pagos/lotes/\d+/items$",        settings.interbanking_service_url, "interbanking:pagos:read"),
    ("GET",    r"^/api/interbanking/pagos/lotes/\d+/estado$",       settings.interbanking_service_url, "interbanking:pagos:read"),
    ("POST",   r"^/api/interbanking/pagos/lotes/\d+/procesar$",     settings.interbanking_service_url, "interbanking:pagos:write"),
    ("GET",    r"^/api/interbanking/pagos/lotes/\d+$",              settings.interbanking_service_url, "interbanking:pagos:read"),
    ("GET",    r"^/api/interbanking/pagos/lotes$",                  settings.interbanking_service_url, "interbanking:pagos:read"),
    ("POST",   r"^/api/interbanking/pagos/lotes$",                  settings.interbanking_service_url, "interbanking:pagos:write"),
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
