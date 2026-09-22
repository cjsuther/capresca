"""Mapeo de rutas → microservicio + permiso requerido."""
import pytest

from app.config import settings
from app.routes.mapping import get_required_permission, get_service_url


@pytest.mark.parametrize("metodo,ruta,servicio,permiso", [
    # Auth: pública, sin permiso, a security
    ("POST", "/api/auth/login", settings.security_service_url, None),
    ("POST", "/api/auth/logout", settings.security_service_url, None),
    # Security
    ("GET", "/api/security/users", settings.security_service_url, "security:users:read"),
    ("POST", "/api/security/users", settings.security_service_url, "security:users:write"),
    ("PUT", "/api/security/users/me/password", settings.security_service_url, None),
    ("PUT", "/api/security/users/12/password", settings.security_service_url, "security:users:write"),
    # Módulos
    ("GET", "/api/cajeros/rules", settings.cajeros_service_url, "cajeros:rules:read"),
    ("PUT", "/api/cajeros/transactions/3/authorize", settings.cajeros_service_url, "cajeros:transactions:authorize"),
    ("GET", "/api/clientes", settings.clientes_service_url, "clientes:clients:read"),
    ("GET", "/api/notifications/unread-count", settings.notifications_service_url, None),
    ("GET", "/api/conciliacion/summary", settings.conciliacion_service_url, "conciliacion:read"),
    ("POST", "/api/liquidaciones/upload", settings.liquidaciones_service_url, "liquidaciones:liq:write"),
    ("GET", "/api/interbanking/cuentas/saldos", settings.interbanking_service_url, "interbanking:cuentas:read"),
    ("POST", "/api/legacy/outbox/drain", settings.legacy_service_url, "legacy:admin:write"),
])
def test_rutas_conocidas(metodo, ruta, servicio, permiso):
    assert get_service_url(metodo, ruta) == servicio
    assert get_required_permission(metodo, ruta) == permiso


@pytest.mark.parametrize("ruta", [
    "/api/desconocido",
    "/api/creditos/no-existe",
    "/api/security",                      # sin el recurso no matchea ninguna entrada
    "/internal/liquidaciones/upload",     # los /internal NUNCA se publican por el gateway
])
def test_rutas_no_mapeadas_no_tienen_destino(ruta):
    assert get_service_url("GET", ruta) is None


@pytest.mark.parametrize("metodo,ruta,permiso", [
    # Una sola área: GET lee (`creditos:read`), el resto escribe (`creditos:write`).
    ("GET", "/api/creditos/contratos/tablero", "creditos:creditos:read"),
    ("POST", "/api/creditos/contratos/originar", "creditos:creditos:write"),
    ("GET", "/api/creditos/creditos/lineas", "creditos:creditos:read"),
    ("GET", "/api/creditos/creditos/consultas/pagos-caja", "creditos:creditos:read"),
    # El padrón de clientes vive en el módulo Clientes: en Créditos queda sólo el espejo.
    ("GET", "/api/creditos/clientes", "creditos:creditos:read"),
    ("PUT", "/api/creditos/clientes/5/perfil-crediticio", "creditos:creditos:write"),
    # Configuración del crédito
    ("GET", "/api/creditos/admin/organismos", "creditos:creditos:read"),
    ("POST", "/api/creditos/admin/lineas", "creditos:creditos:write"),
    ("POST", "/api/creditos/admin/parametros", "creditos:creditos:write"),
    ("GET", "/api/creditos/impuestos", "creditos:creditos:read"),
    ("GET", "/api/creditos/indices", "creditos:creditos:read"),
    # Caja: sólo el recibo y los pendientes de cobro que muestran las pantallas de créditos
    ("GET", "/api/creditos/caja/recibos/9/pdf", "creditos:creditos:read"),
    ("GET", "/api/creditos/caja/pendientes-cobro", "creditos:creditos:read"),
    # Autorización fina en el módulo
    ("GET", "/api/creditos/aprobaciones/inbox", "creditos:*"),
    ("POST", "/api/creditos/aprobaciones/pendientes/abc/aprobar", "creditos:*"),
    ("POST", "/api/creditos/productos/abc/estado", "creditos:*"),
    ("POST", "/api/creditos/solicitudes/abc/estado", "creditos:*"),
])
def test_rutas_de_creditos(metodo, ruta, permiso):
    assert get_service_url(metodo, ruta) == settings.creditos_service_url
    assert get_required_permission(metodo, ruta) == permiso


@pytest.mark.parametrize("ruta", [
    "/api/creditos/portal/auth/login",        # el portal ciudadano va directo por nginx
    "/api/creditos/admin/usuarios",           # el ABM de usuarios se administra en Seguridad
    "/api/creditos/admin/auditoria",
    "/api/creditos/auth/mis-permisos",        # los permisos los resuelve el gateway
    # Áreas de CCyPP que no se migraron a Portezuelo
    "/api/creditos/caja/cobrar",
    "/api/creditos/caja/cierre",
    "/api/creditos/egresos/ordenes",
    "/api/creditos/contabilidad/balance",
    "/api/creditos/seguros/polizas",
    "/api/creditos/despacho/resoluciones",
    "/api/creditos/mesa/turnos",
    "/api/creditos/juegos/maestro",
    "/api/creditos/controles-version",
    "/api/creditos/migradores",
    # Pasaron a Configuraciones
    "/api/creditos/feriados",
    "/api/creditos/workflow",
    "/api/creditos/impuestos/3/baja",
])
def test_rutas_de_creditos_que_no_se_publican(ruta):
    assert get_service_url("GET", ruta) is None
    assert get_service_url("POST", ruta) is None


@pytest.mark.parametrize("metodo,ruta,permiso", [
    ("GET", "/api/configuraciones/impuestos", "configuraciones:impuestos:read"),
    ("POST", "/api/configuraciones/impuestos/4/baja", "configuraciones:impuestos:write"),
    ("PUT", "/api/configuraciones/indices/2", "configuraciones:indices:write"),
    ("GET", "/api/configuraciones/feriados/paises", "configuraciones:feriados:read"),
    ("POST", "/api/configuraciones/feriados/importar", "configuraciones:feriados:write"),
    ("GET", "/api/configuraciones/workflow", "configuraciones:workflow:read"),
    ("DELETE", "/api/configuraciones/workflow/niveles/3", "configuraciones:workflow:write"),
])
def test_rutas_de_configuraciones(metodo, ruta, permiso):
    assert get_service_url(metodo, ruta) == settings.configuraciones_service_url
    assert get_required_permission(metodo, ruta) == permiso


@pytest.mark.parametrize("ruta", ["/internal/configuraciones/impuestos", "/api/configuraciones/otra-cosa"])
def test_configuraciones_no_publica_lo_interno_ni_rutas_desconocidas(ruta):
    assert get_service_url("GET", ruta) is None


@pytest.mark.parametrize("metodo,ruta,permiso", [
    ("GET", "/api/clientes/7/documentos", "clientes:clients:read"),
    ("GET", "/api/clientes/7/documentos/12", "clientes:clients:read"),
    ("POST", "/api/clientes/7/documentos", "clientes:clients:write"),
    ("DELETE", "/api/clientes/7/documentos/12", "clientes:clients:write"),
    ("POST", "/api/creditos/solicitudes/abc/documentos/copiar-al-cliente", "creditos:creditos:write"),
])
def test_documentos_del_cliente(metodo, ruta, permiso):
    assert get_required_permission(metodo, ruta) == permiso


def test_la_copia_interna_de_documentos_no_se_publica():
    assert get_service_url("POST", "/internal/clientes/7/documentos") is None


@pytest.mark.parametrize("metodo,ruta,permiso", [
    ("GET", "/api/tesoreria/lotes", "tesoreria:lotes:read"),
    ("GET", "/api/tesoreria/lotes/12", "tesoreria:lotes:read"),
    ("GET", "/api/tesoreria/lotes/cuentas-origen", "tesoreria:lotes:read"),
    ("POST", "/api/tesoreria/lotes", "tesoreria:lotes:write"),
    ("POST", "/api/tesoreria/lotes/12/pagos/3/excluir", "tesoreria:lotes:write"),
    ("POST", "/api/tesoreria/lotes/12/aprobar", "tesoreria:*"),
    ("POST", "/api/tesoreria/lotes/12/enviar", "tesoreria:*"),
    ("POST", "/api/tesoreria/lotes/12/pagos/3/resolver", "tesoreria:*"),
])
def test_rutas_de_tesoreria(metodo, ruta, permiso):
    assert get_service_url(metodo, ruta) == settings.tesoreria_service_url
    assert get_required_permission(metodo, ruta) == permiso


@pytest.mark.parametrize("metodo,ruta", [("POST", "/internal/tesoreria/lotes"), ("DELETE", "/api/tesoreria/lotes/12"),
                                         ("PUT", "/api/tesoreria/lotes/12")])
def test_tesoreria_no_publica_lo_interno_ni_otras_operaciones(metodo, ruta):
    assert get_service_url(metodo, ruta) is None


@pytest.mark.parametrize("metodo,ruta,permiso", [
    ("GET", "/api/security/groups", "security:groups:read"),
    ("POST", "/api/security/groups", "security:groups:write"),
    ("PUT", "/api/security/groups/4", "security:groups:write"),
    ("DELETE", "/api/security/groups/4", "security:groups:write"),
    ("POST", "/api/security/groups/4/roles", "security:groups:write"),
    ("POST", "/api/security/groups/4/users", "security:groups:write"),
    ("POST", "/api/security/users/9/groups", "security:groups:write"),
    ("GET", "/api/security/users/9/effective-permissions", "security:users:read"),
])
def test_rutas_de_grupos(metodo, ruta, permiso):
    assert get_service_url(metodo, ruta) == settings.security_service_url
    assert get_required_permission(metodo, ruta) == permiso


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/api/auditoria/eventos"),
    ("GET", "/api/auditoria/eventos/12"),
    ("GET", "/api/auditoria/eventos/resumen"),
    ("GET", "/api/auditoria/registros/creditos/Contrato/CTO-1"),
])
def test_la_auditoria_se_consulta_con_su_permiso(metodo, ruta):
    assert get_service_url(metodo, ruta) == settings.auditoria_service_url
    assert get_required_permission(metodo, ruta) == "auditoria:eventos:read"


@pytest.mark.parametrize("metodo,ruta", [("DELETE", "/api/auditoria/eventos/12"),
                                         ("POST", "/api/auditoria/eventos"),
                                         ("PUT", "/api/auditoria/eventos/12"),
                                         ("POST", "/internal/auditoria/eventos")])
def test_el_registro_de_auditoria_no_se_escribe_desde_afuera(metodo, ruta):
    assert get_service_url(metodo, ruta) is None


@pytest.mark.parametrize("metodo,ruta,permiso", [
    ("GET", "/api/contabilidad/asientos", "contabilidad:asientos:read"),
    ("GET", "/api/contabilidad/libros/diario", "contabilidad:asientos:read"),
    ("GET", "/api/contabilidad/transacciones/sin-definir", "contabilidad:asientos:read"),
    ("POST", "/api/contabilidad/asientos", "contabilidad:asientos:write"),
    ("POST", "/api/contabilidad/asientos/4/anular", "contabilidad:asientos:write"),
    ("POST", "/api/contabilidad/transacciones/reprocesar", "contabilidad:asientos:write"),
    ("POST", "/api/contabilidad/cuentas", "contabilidad:definiciones:write"),
    ("PUT", "/api/contabilidad/definiciones/4", "contabilidad:definiciones:write"),
    ("POST", "/api/contabilidad/definiciones/4/probar", "contabilidad:definiciones:write"),
    ("POST", "/api/contabilidad/ejercicios", "contabilidad:ejercicios:write"),
    ("POST", "/api/contabilidad/ejercicios/4/cerrar", "contabilidad:ejercicios:write"),
])
def test_rutas_de_contabilidad(metodo, ruta, permiso):
    assert get_service_url(metodo, ruta) == settings.contabilidad_service_url
    assert get_required_permission(metodo, ruta) == permiso


def test_las_transacciones_contables_solo_entran_por_la_api_interna():
    """Ningún módulo manda asientos ni transacciones por el gateway: van por la red interna."""
    assert get_service_url("POST", "/internal/contabilidad/transacciones") is None

