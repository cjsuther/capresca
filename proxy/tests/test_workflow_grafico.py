"""Workflow gráfico: permisos del gateway y step-up (borrador sin step-up, publicar con step-up).

Archivo aparte de test_mapping/test_stepup para no mezclar estos casos con los del resto de módulos."""
import pytest

from app.config import settings
from app.routes.mapping import get_required_permission, get_service_url
from app.routes.stepup import REGLA_SEGURIDAD, SIN_STEP_UP, regla_step_up, requiere_step_up

B = "/api/configuraciones/workflow"


@pytest.mark.parametrize("metodo,ruta,permiso", [
    ("GET", f"{B}/procesos", "configuraciones:workflow:read"),
    ("GET", f"{B}/versiones/4", "configuraciones:workflow:read"),
    ("GET", f"{B}/comparar", "configuraciones:workflow:read"),
    ("POST", f"{B}/procesos/2/borrador", "configuraciones:workflow:write"),
    ("PUT", f"{B}/versiones/4", "configuraciones:workflow:write"),
    ("DELETE", f"{B}/versiones/4", "configuraciones:workflow:write"),
    ("POST", f"{B}/versiones/4/publicar", "configuraciones:workflow:publish"),
    ("POST", f"{B}/versiones/4/retirar", "configuraciones:workflow:publish"),
    ("POST", f"{B}/procesos/2/habilitado", "configuraciones:workflow:publish"),
])
def test_permisos_del_workflow_grafico(metodo, ruta, permiso):
    assert get_service_url(metodo, ruta) == settings.configuraciones_service_url
    assert get_required_permission(metodo, ruta) == permiso


@pytest.mark.parametrize("metodo,ruta", [
    ("POST", f"{B}/procesos/2/borrador"), ("PUT", f"{B}/versiones/4"), ("DELETE", f"{B}/versiones/4"),
    ("GET", f"{B}/procesos"),
])
def test_los_borradores_no_piden_step_up(metodo, ruta):
    assert requiere_step_up(metodo, ruta) is None


@pytest.mark.parametrize("metodo,ruta,texto", [
    ("POST", f"{B}/versiones/4/publicar", "Publicar o retirar"),
    ("POST", f"{B}/versiones/4/retirar", "Publicar o retirar"),
    ("POST", f"{B}/procesos/2/habilitado", "Habilitar o deshabilitar"),
    # Lo que no es borrador sigue con la regla general de Configuraciones.
    ("PUT", f"{B}/reglas/1", "Cambiar la configuración"),
    ("POST", f"{B}/versiones/4/otra-cosa", "Cambiar la configuración"),
    ("PUT", f"{B}/versiones/4/publicar", "Cambiar la configuración"),
])
def test_publicar_y_lo_demas_si_piden_step_up(metodo, ruta, texto):
    assert texto in (requiere_step_up(metodo, ruta) or "")


@pytest.mark.parametrize("metodo,rx", SIN_STEP_UP)
def test_la_excepcion_de_borradores_nunca_alcanza_a_seguridad(metodo, rx):
    assert rx.startswith(r"^/api/configuraciones/workflow/")
    for ruta in ("/api/security/users/1", "/api/security/roles/1", "/api/security/groups/1"):
        assert regla_step_up(metodo, ruta) is REGLA_SEGURIDAD
