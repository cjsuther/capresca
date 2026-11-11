"""Seguridad: TODA escritura sobre /api/security/... exige step-up y, sin 2FA activo, se bloquea aunque la
transición (TOKENSERVER_STEPUP_SIN_2FA=permitir) deje pasar al resto de los módulos."""
import ast
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from jose import jwt

from app.config import settings
from app.routes.mapping import ROUTE_MAP, get_service_url
from app.routes.stepup import (
    MENSAJE_SEGURIDAD_SIN_2FA, REGLA_SEGURIDAD, regla_step_up, requiere_step_up,
)
from tests.test_stepup import sesion, step_up

SECURITY = Path(__file__).resolve().parents[2] / "modules" / "security" / "app"
ESCRITURA = ("post", "put", "patch", "delete")
ADMIN = {"security": ["users:read", "users:write", "roles:read", "roles:write", "groups:read", "groups:write"],
         "tesoreria": ["lotes:read", "lotes:write"]}


def _rutas_de_security() -> list[tuple[str, str]]:
    """(MÉTODO, ruta completa) de cada endpoint de escritura de security, leídos del código fuente:
    prefijo del include_router en main.py + prefijo del APIRouter + ruta del decorador."""
    main = ast.parse((SECURITY / "main.py").read_text())
    prefijo_include = {}
    for nodo in ast.walk(main):
        if isinstance(nodo, ast.Call) and getattr(nodo.func, "attr", "") == "include_router":
            modulo = nodo.args[0].value.id                       # auth.router → "auth"
            kw = {k.arg: k.value.value for k in nodo.keywords if isinstance(k.value, ast.Constant)}
            prefijo_include[modulo] = kw.get("prefix", "")
    rutas = []
    for archivo in sorted((SECURITY / "routers").glob("*.py")):
        if archivo.stem not in prefijo_include:
            continue
        arbol = ast.parse(archivo.read_text())
        prefijo_router = ""
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "APIRouter":
                prefijo_router = next((k.value.value for k in nodo.keywords if k.arg == "prefix"), "")
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in nodo.decorator_list:
                if (isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") in ESCRITURA
                        and getattr(dec.func.value, "id", "") == "router"):
                    ruta = prefijo_include[archivo.stem] + prefijo_router + dec.args[0].value
                    # {user_id} → 7 (y "me" se queda como está)
                    rutas.append((dec.func.attr.upper(), re.sub(r"\{[^}]+\}", "7", ruta)))
    return rutas


RUTAS = _rutas_de_security() if SECURITY.exists() else []


@pytest.fixture
def transicion(monkeypatch):
    """Lo que está en producción: 2FA prendido y, en general, sin 2FA se permite."""
    monkeypatch.setattr(settings, "tokenserver_enabled", True)
    monkeypatch.setattr(settings, "tokenserver_stepup_sin_2fa", "permitir")


def test_se_encontraron_las_rutas_de_security():
    if not SECURITY.exists():
        pytest.skip("modules/security no está al lado de proxy/ (correr desde el repo completo)")
    metodos = {m for m, _ in RUTAS}
    assert len(RUTAS) >= 25 and {"POST", "PUT", "DELETE"} <= metodos, RUTAS


@pytest.mark.parametrize("metodo,ruta", [r for r in RUTAS if r[1].startswith("/api/security")])
def test_toda_escritura_de_security_exige_step_up_y_bloquea_sin_2fa(metodo, ruta):
    regla = regla_step_up(metodo, ruta)
    assert regla is REGLA_SEGURIDAD, f"{metodo} {ruta} no está cubierta"
    assert regla.sin_2fa == "bloquear"
    assert get_service_url(metodo, ruta), f"{metodo} {ruta} no está publicada en mapping.py"


@pytest.mark.parametrize("metodo,ruta", [r for r in RUTAS if r[1].startswith("/api/auth")])
def test_las_rutas_de_auth_y_del_propio_2fa_quedan_exceptuadas(metodo, ruta):
    assert regla_step_up(metodo, ruta) is None


def test_ninguna_escritura_de_security_vive_fuera_de_api_security_o_api_auth():
    fuera = [r for r in RUTAS if not r[1].startswith(("/api/security/", "/api/auth/"))]
    assert fuera == []


def test_el_gateway_no_publica_escrituras_de_security_con_otro_prefijo():
    # Toda entrada de mapping.py que lleva a security sin ser lectura empieza con /api/security o /api/auth.
    for metodo, patron, url, _ in ROUTE_MAP:
        if url == settings.security_service_url and metodo != "GET":
            assert patron.startswith((r"^/api/security", r"^/api/auth/")), patron


@pytest.mark.parametrize("metodo", ["POST", "PUT", "PATCH", "DELETE", "MERGE"])
def test_una_ruta_nueva_de_security_queda_cubierta_sola(metodo):
    assert regla_step_up(metodo, "/api/security/algo-nuevo/9/accion") is REGLA_SEGURIDAD
    assert regla_step_up(metodo, "/api/security") is REGLA_SEGURIDAD


@pytest.mark.parametrize("metodo", ["GET", "HEAD", "OPTIONS"])
def test_las_lecturas_de_security_no_piden_nada(metodo):
    assert regla_step_up(metodo, "/api/security/users") is None


def test_descripciones_puntuales():
    assert requiere_step_up("PUT", "/api/security/users/me/password") == "Cambiar tu contraseña"
    assert requiere_step_up("DELETE", "/api/security/users/3/2fa") == "Resetear el doble factor de un usuario"
    assert requiere_step_up("PATCH", "/api/security/x") == "Hacer cambios en Seguridad"


# ── Por HTTP, con la política de transición ("permitir") ─────────────────────────────────────────
@pytest.mark.parametrize("metodo,ruta", [
    ("POST", "/api/security/users"), ("PUT", "/api/security/users/3"), ("DELETE", "/api/security/users/3"),
    ("POST", "/api/security/roles/2/permissions"), ("POST", "/api/security/groups/2/users"),
    ("PUT", "/api/security/users/me/password"), ("DELETE", "/api/security/users/3/2fa"),
])
def test_sin_2fa_seguridad_se_bloquea_aunque_la_transicion_permita(client, permisos, transicion, metodo, ruta):
    llamadas = permisos(ADMIN)
    tok, _ = sesion(amr=("pwd",))
    r = client.request(metodo, ruta, headers={"Authorization": f"Bearer {tok}"}, json={})
    assert r.status_code == 403
    assert r.json()["code"] == "2fa_requerido"
    assert r.json()["detail"] == MENSAJE_SEGURIDAD_SIN_2FA
    assert not any(c["metodo"] == metodo for c in llamadas.llamadas)      # no llegó a security


def test_sin_2fa_el_resto_de_los_modulos_sigue_en_transicion(client, permisos, transicion):
    permisos(ADMIN)
    tok, _ = sesion(amr=None)
    r = client.post("/api/tesoreria/lotes/1/aprobar", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_sin_2fa_un_token_de_step_up_no_alcanza_si_no_es_valido(client, permisos, transicion):
    permisos(ADMIN)
    tok, jti = sesion(amr=None)
    r = client.post("/api/security/users", headers={"Authorization": f"Bearer {tok}", "X-2FA-Token": "basura"})
    assert r.json()["code"] == "2fa_requerido"


def test_con_2fa_pide_el_codigo_y_con_token_pasa(client, permisos, transicion):
    permisos(ADMIN)
    tok, jti = sesion()
    h = {"Authorization": f"Bearer {tok}"}
    r = client.post("/api/security/users", headers=h, json={})
    assert r.status_code == 403 and r.json()["code"] == "step_up_requerido"
    assert r.json()["operacion"] == "Crear un usuario"
    assert client.post("/api/security/users", headers={**h, "X-2FA-Token": step_up(sid=jti)}, json={}).status_code == 200


def test_el_reset_del_2fa_de_otro_usuario_exige_el_token_del_admin(client, permisos, transicion):
    permisos(ADMIN)
    tok, jti = sesion(user_id=7)
    h = {"Authorization": f"Bearer {tok}"}
    r = client.delete("/api/security/users/3/2fa", headers=h)
    assert r.status_code == 403 and r.json()["code"] == "step_up_requerido"
    # Un token de step-up de OTRO usuario (el reseteado, p.ej.) no sirve.
    r = client.delete("/api/security/users/3/2fa", headers={**h, "X-2FA-Token": step_up(user_id=3, sid=jti)})
    assert r.status_code == 403
    r = client.delete("/api/security/users/3/2fa", headers={**h, "X-2FA-Token": step_up(user_id=7, sid=jti)})
    assert r.status_code == 200


def test_cambiar_la_propia_contrasena_exige_step_up(client, permisos, transicion):
    permisos(ADMIN)
    tok, jti = sesion()
    h = {"Authorization": f"Bearer {tok}"}
    r = client.put("/api/security/users/me/password", headers=h, json={})
    assert r.status_code == 403 and r.json()["operacion"] == "Cambiar tu contraseña"
    r = client.put("/api/security/users/me/password", headers={**h, "X-2FA-Token": step_up(sid=jti)}, json={})
    assert r.status_code == 200


@pytest.mark.parametrize("ruta", ["/api/auth/2fa/enrolar", "/api/auth/2fa/activar", "/api/auth/2fa/step-up",
                                  "/api/auth/2fa/desactivar", "/api/auth/2fa/codigos-recuperacion",
                                  "/api/auth/logout"])
def test_sin_2fa_puede_enrolarse_y_gestionar_su_propio_2fa(client, permisos, transicion, ruta, monkeypatch):
    monkeypatch.setattr(settings, "tokenserver_stepup_sin_2fa", "bloquear")
    permisos(ADMIN)
    tok, _ = sesion(amr=None)
    assert client.post(ruta, headers={"Authorization": f"Bearer {tok}"}, json={}).status_code == 200


def test_apagado_no_cambia_nada(client, permisos, monkeypatch):
    monkeypatch.setattr(settings, "tokenserver_enabled", False)
    permisos(ADMIN)
    tok, _ = sesion(amr=None)
    assert client.post("/api/security/users", headers={"Authorization": f"Bearer {tok}"}, json={}).status_code == 200
