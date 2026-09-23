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
    """Créditos publica sólo el circuito de créditos: todo pide `creditos:read` (GET) o `creditos:write`.
    Las áreas de CCyPP que no se migraron (caja, contabilidad, tesorería, seguros, despacho, mesa, juegos,
    general, seguridad) no tienen rutas: el gateway no las reenvía (404)."""
    url = settings.creditos_service_url
    base = r"^/api/creditos"
    return [
        # Aprobaciones: el módulo exige el rol de aprobación que pide cada nivel del workflow.
        ("GET",  base + r"/aprobaciones/inbox$",                           url, "creditos:*"),
        ("POST", base + r"/aprobaciones/pendientes/[^/]+/(aprobar|rechazar)$", url, "creditos:*"),
        # Cambios de estado: mezclan acciones de edición y de aprobación; el módulo las gatea por acción.
        ("POST", base + r"/productos/[^/]+/estado$",                       url, "creditos:*"),
        ("POST", base + r"/solicitudes/[^/]+/estado$",                     url, "creditos:*"),
        # Catálogos de Configuraciones que usa el armado de productos: sólo lectura (Créditos los trae
        # de Configuraciones; se editan allá, con sus permisos).
        ("GET",  base + r"/(impuestos|indices)$",                         url, "creditos:creditos:read"),
        *_creditos_area(base + r"/(clientes|creditos|solicitudes|productos|contratos|sistema-calculos)(/|$)",
                        "creditos"),
        # De `admin` y `caja` sólo se publica lo que usa el circuito de créditos.
        *_creditos_area(base + r"/admin/(lineas|organismos|parametros)(/|$)", "creditos"),
        *_creditos_area(base + r"/caja/(recibos|pendientes-cobro)(/|$)", "creditos"),
    ]


def _configuraciones_rutas() -> list:
    """Cada catálogo tiene su par de permisos: tener `indices:write` no habilita a tocar impuestos, y
    el workflow (quién aprueba) se administra con un permiso propio, aparte de operar los módulos."""
    url = settings.configuraciones_service_url
    base = r"^/api/configuraciones"
    rutas = []
    for catalogo in ("impuestos", "indices", "feriados", "workflow"):
        rx = base + rf"/{catalogo}(/|$)"
        rutas += [("GET", rx, url, f"configuraciones:{catalogo}:read"),
                  (None, rx, url, f"configuraciones:{catalogo}:write")]
    return rutas


# (method, pattern_regex) → (service_base_url, required_permission | None)
ROUTE_MAP = [
    # ── Auth (sin permiso requerido) ────────────────────────────
    (None,   r"^/api/auth/",                settings.security_service_url, None),

    # ── Security ────────────────────────────────────────────────
    ("GET",  r"^/api/security/users",       settings.security_service_url, "security:users:read"),
    ("PUT",  r"^/api/security/users/me/password$",    settings.security_service_url, None),
    ("PUT",  r"^/api/security/users/\d+/password$",  settings.security_service_url, "security:users:write"),
    ("POST", r"^/api/security/users/\d+/roles$",     settings.security_service_url, "security:users:write"),
    ("POST", r"^/api/security/users/\d+/groups$",    settings.security_service_url, "security:groups:write"),
    ("POST", r"^/api/security/users$",               settings.security_service_url, "security:users:write"),
    ("PUT",  r"^/api/security/users/",               settings.security_service_url, "security:users:write"),
    ("DELETE", r"^/api/security/users/",             settings.security_service_url, "security:users:write"),
    ("GET",    r"^/api/security/roles",         settings.security_service_url, "security:roles:read"),
    ("POST",   r"^/api/security/roles/\d+/permissions$", settings.security_service_url, "security:roles:write"),
    ("POST",   r"^/api/security/roles$",               settings.security_service_url, "security:roles:write"),
    ("PUT",    r"^/api/security/roles/",        settings.security_service_url, "security:roles:write"),
    ("DELETE", r"^/api/security/roles/",        settings.security_service_url, "security:roles:write"),
    ("GET",    r"^/api/security/groups$",       settings.security_service_url, "security:groups:read"),
    ("POST",   r"^/api/security/groups(/\d+/(roles|users))?$", settings.security_service_url, "security:groups:write"),
    ("PUT",    r"^/api/security/groups/\d+$",   settings.security_service_url, "security:groups:write"),
    ("DELETE", r"^/api/security/groups/\d+$",   settings.security_service_url, "security:groups:write"),
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
    # Documentos del cliente (DNI, recibo…): verlos pide lectura; cargarlos o borrarlos, escritura.
    ("PUT",    r"^/api/clientes/\d+/padron$",           settings.clientes_service_url, "clientes:clients:write"),
    # Padrón: importación masiva del maestro del sistema anterior (permiso propio).
    ("POST",   r"^/api/clientes/padron/importaciones$",  settings.clientes_service_url, "clientes:padron:importar"),
    ("GET",    r"^/api/clientes/padron/importaciones(/\d+(/rechazos)?)?$", settings.clientes_service_url, "clientes:padron:importar"),
    ("GET",    r"^/api/clientes/\d+/documentos(/\d+)?$",  settings.clientes_service_url, "clientes:clients:read"),
    ("POST",   r"^/api/clientes/\d+/documentos$",         settings.clientes_service_url, "clientes:clients:write"),
    ("DELETE", r"^/api/clientes/\d+/documentos/\d+$",     settings.clientes_service_url, "clientes:clients:write"),
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

    # ── Configuraciones: un par read/write por catálogo (impuestos, índices, feriados, workflow) ──
    *_configuraciones_rutas(),

    # ── Contabilidad: consultar libros / registrar asientos / definir imputaciones / ejercicios ──
    ("GET",  r"^/api/contabilidad/",                                    settings.contabilidad_service_url, "contabilidad:asientos:read"),
    ("POST", r"^/api/contabilidad/asientos$",                           settings.contabilidad_service_url, "contabilidad:asientos:write"),
    ("POST", r"^/api/contabilidad/asientos/\d+/anular$",                settings.contabilidad_service_url, "contabilidad:asientos:write"),
    ("POST", r"^/api/contabilidad/transacciones/reprocesar$",           settings.contabilidad_service_url, "contabilidad:asientos:write"),
    ("POST", r"^/api/contabilidad/asientos/\d+/publicar$",              settings.contabilidad_service_url, "contabilidad:asientos:write"),
    ("DELETE", r"^/api/contabilidad/asientos/\d+$",                     settings.contabilidad_service_url, "contabilidad:asientos:write"),
    ("POST", r"^/api/contabilidad/conciliacion/",                       settings.contabilidad_service_url, "contabilidad:asientos:write"),
    ("DELETE", r"^/api/contabilidad/conciliacion/extracto/\d+$",        settings.contabilidad_service_url, "contabilidad:asientos:write"),
    ("POST", r"^/api/contabilidad/(cuentas|centros|definiciones|empresas)$", settings.contabilidad_service_url, "contabilidad:definiciones:write"),
    ("PUT",  r"^/api/contabilidad/(cuentas|definiciones|centros|empresas)/\d+$", settings.contabilidad_service_url, "contabilidad:definiciones:write"),
    ("DELETE", r"^/api/contabilidad/cuentas/\d+$",                      settings.contabilidad_service_url, "contabilidad:definiciones:write"),
    ("POST", r"^/api/contabilidad/definiciones/\d+/probar$",            settings.contabilidad_service_url, "contabilidad:definiciones:write"),
    ("POST", r"^/api/contabilidad/ejercicios$",                         settings.contabilidad_service_url, "contabilidad:ejercicios:write"),
    ("POST", r"^/api/contabilidad/ejercicios/\d+/(cerrar|reabrir|apertura)$", settings.contabilidad_service_url, "contabilidad:ejercicios:write"),

    # ── Auditoría: sólo consulta (el registro no se edita ni se borra desde ningún lado) ──
    ("GET",  r"^/api/auditoria/eventos(/\d+|/resumen)?$",               settings.auditoria_service_url, "auditoria:eventos:read"),
    ("GET",  r"^/api/auditoria/registros/[^/]+/[^/]+/[^/]+$",           settings.auditoria_service_url, "auditoria:eventos:read"),

    # ── Tesorería: ver lotes pide lectura; aprobar/rechazar y enviar los valida el módulo (workflow y
    #    permiso de envío), así el gateway sólo exige ser del módulo para esas acciones. ──
    ("GET",  r"^/api/tesoreria/lotes(/\d+)?$",                          settings.tesoreria_service_url, "tesoreria:lotes:read"),
    ("GET",  r"^/api/tesoreria/lotes/cuentas-origen$",                  settings.tesoreria_service_url, "tesoreria:lotes:read"),
    ("POST", r"^/api/tesoreria/lotes$",                                  settings.tesoreria_service_url, "tesoreria:lotes:write"),
    ("POST", r"^/api/tesoreria/lotes/\d+/pagos/\d+/(excluir|incluir)$",  settings.tesoreria_service_url, "tesoreria:lotes:write"),
    ("POST", r"^/api/tesoreria/lotes/\d+/(aprobar|rechazar)$",           settings.tesoreria_service_url, "tesoreria:*"),
    ("POST", r"^/api/tesoreria/lotes/\d+/(enviar|actualizar)$",          settings.tesoreria_service_url, "tesoreria:*"),
    ("POST", r"^/api/tesoreria/lotes/\d+/pagos/\d+/(reintentar|resolver)$", settings.tesoreria_service_url, "tesoreria:*"),
]


def get_service_url(method: str, path: str) -> str | None:
    for entry in ROUTE_MAP:
        m, pattern, service_url, _ = entry
        if (m is None or m == method) and re.match(pattern, path):
            return service_url
    return None


def get_required_permission(method: str, path: str) -> str | tuple[str, ...] | None:
    """Permiso exigido para la ruta. Una tupla significa "alcanza con cualquiera de estos"."""
    for entry in ROUTE_MAP:
        m, pattern, _, permission = entry
        if (m is None or m == method) and re.match(pattern, path):
            return permission
    return None
