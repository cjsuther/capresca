"""Step-up en el gateway: operaciones sensibles exigen el código del doble factor otra vez."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import settings
from app.middleware import auth as auth_mod
from app.routes.mapping import get_service_url
from app.routes.stepup import STEP_UP_RUTAS, requiere_step_up

# Vector fijo: security (app/services/auth_service.py::clave_derivada) deriva exactamente esta clave para
# JWT_SECRET="secreto-de-test". Si una de las dos derivaciones cambia, este test lo marca.
CLAVE_STEP_UP_TEST = "00233bba2439943fccd602ebea4f66fc01d3132d394437b835ca03c62f89f5c1"

TESORERIA = {"tesoreria": ["lotes:read", "lotes:write"]}


def sesion(user_id=7, amr=("pwd", "otp"), jti=None):
    jti = jti or uuid.uuid4().hex
    payload = {"sub": str(user_id), "username": "ana", "jti": jti,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=60)}
    if amr:
        payload["amr"] = list(amr)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), jti


def step_up(user_id=7, sid="", minutos=5, clave=None, scope="step_up"):
    payload = {"sub": str(user_id), "scope": scope, "sid": sid, "jti": uuid.uuid4().hex,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=minutos)}
    return jwt.encode(payload, clave or CLAVE_STEP_UP_TEST, algorithm="HS256")


@pytest.fixture
def prendido(monkeypatch):
    monkeypatch.setattr(settings, "tokenserver_enabled", True)
    monkeypatch.setattr(settings, "tokenserver_stepup_sin_2fa", "bloquear")


def test_la_clave_derivada_coincide_con_la_de_security():
    assert settings.jwt_secret == "secreto-de-test"
    assert auth_mod._clave_step_up() == CLAVE_STEP_UP_TEST


# ── La lista ─────────────────────────────────────────────────────────────────────────────────────
EJEMPLOS = [
    ("POST", "/api/tesoreria/lotes/12/aprobar"), ("POST", "/api/tesoreria/lotes/12/enviar"),
    ("POST", "/api/tesoreria/lotes/12/reintentar-fallidos"), ("POST", "/api/tesoreria/lotes/1/pagos/3/reintentar"),
    ("POST", "/api/tesoreria/lotes/1/pagos/3/resolver"), ("POST", "/api/tesoreria/ordenes-pago/4/anular"),
    ("POST", "/api/interbanking/transferencias"), ("POST", "/api/interbanking/config"),
    ("POST", "/api/security/users"), ("PUT", "/api/security/users/3"), ("DELETE", "/api/security/users/3"),
    ("PUT", "/api/security/users/3/password"), ("POST", "/api/security/users/3/roles"),
    ("POST", "/api/security/users/3/groups"), ("DELETE", "/api/security/users/3/2fa"),
    ("POST", "/api/security/roles"), ("POST", "/api/security/roles/2/permissions"),
    ("PUT", "/api/security/roles/2"), ("DELETE", "/api/security/roles/2"),
    ("POST", "/api/security/groups"), ("POST", "/api/security/groups/2/users"), ("PUT", "/api/security/groups/2"),
    ("DELETE", "/api/security/groups/2"),
    ("POST", "/api/configuraciones/impuestos"), ("PUT", "/api/configuraciones/impuestos/5"),
    ("PUT", "/api/configuraciones/workflow/reglas/1"), ("DELETE", "/api/configuraciones/workflow/niveles/1"),
    ("POST", "/api/configuraciones/indices/BADLAR/valores"),
    ("POST", "/api/creditos/aprobaciones/pendientes/9/aprobar"), ("POST", "/api/creditos/contratos/9/desembolsar"),
    ("POST", "/api/creditos/contratos/liquidar-lote"), ("POST", "/api/creditos/contratos/lotes-liquidacion/2/cerrar"),
    ("POST", "/api/creditos/contratos/9/actividad/4/reversar"), ("POST", "/api/creditos/creditos/9/cancelar"),
    ("PUT", "/api/creditos/solicitudes/9/cbu"),
    ("POST", "/api/clientes/5/cbus"), ("PUT", "/api/clientes/5/cbus/2"), ("DELETE", "/api/clientes/5/cbus/2"),
    ("POST", "/api/conciliacion/records/5/adjustments"),
    ("PUT", "/api/cajeros/transactions/5/authorize"), ("DELETE", "/api/cajeros/transactions/5"),
    ("POST", "/api/cajeros/rules"), ("DELETE", "/api/cajeros/rules/5"),
    ("POST", "/api/contabilidad/asientos/5/anular"), ("DELETE", "/api/contabilidad/asientos/5"),
    ("POST", "/api/contabilidad/ejercicios/5/cerrar"), ("POST", "/api/contabilidad/ejercicios/5/reabrir"),
]


@pytest.mark.parametrize("metodo,ruta", EJEMPLOS)
def test_cada_operacion_sensible_exige_step_up_y_existe_en_el_gateway(metodo, ruta):
    assert requiere_step_up(metodo, ruta)
    assert get_service_url(metodo, ruta), "la ruta con step-up no está publicada en mapping.py"


def test_cada_entrada_de_la_lista_tiene_un_ejemplo():
    cubiertas = {(m, rx) for m, rx, _ in STEP_UP_RUTAS
                 if any(m == em and __import__("re").match(rx, er) for em, er in EJEMPLOS)}
    faltan = [(m, rx) for m, rx, _ in STEP_UP_RUTAS if (m, rx) not in cubiertas
              and m != "PATCH"]          # configuraciones no usa PATCH hoy; queda por las dudas
    assert faltan == []


@pytest.mark.parametrize("metodo,ruta", [
    ("GET", "/api/tesoreria/lotes/12"), ("POST", "/api/tesoreria/lotes"), ("POST", "/api/tesoreria/lotes/12/rechazar"),
    ("POST", "/api/tesoreria/lotes/12/actualizar"), ("GET", "/api/security/users"),
    ("PUT", "/api/security/users/me/password"), ("POST", "/api/interbanking/transferencias/validar"),
    ("POST", "/api/interbanking/config/test"), ("POST", "/api/configuraciones/feriados"),
    ("GET", "/api/configuraciones/impuestos"), ("PUT", "/api/cajeros/transactions/5/reject"),
    ("POST", "/api/auth/2fa/step-up"), ("POST", "/api/auth/login"),
])
def test_lo_que_no_es_sensible_no_pide_step_up(metodo, ruta):
    assert requiere_step_up(metodo, ruta) is None


# ── El middleware ────────────────────────────────────────────────────────────────────────────────
def test_apagado_no_se_pide_nada(client, permisos, monkeypatch):
    monkeypatch.setattr(settings, "tokenserver_enabled", False)
    permisos(TESORERIA)
    tok, _ = sesion(amr=None)
    r = client.post("/api/tesoreria/lotes/1/aprobar", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200


def test_con_2fa_sin_token_de_step_up_pide_el_codigo(client, permisos, prendido):
    llamadas = permisos(TESORERIA)
    tok, _ = sesion()
    r = client.post("/api/tesoreria/lotes/1/aprobar", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    assert r.json()["code"] == "step_up_requerido"
    assert r.json()["operacion"] == "Aprobar un lote de pagos"
    assert not any(c["metodo"] == "POST" for c in llamadas.llamadas)      # no llegó a tesorería


def test_con_token_de_step_up_valido_pasa_y_no_se_reenvia_el_header(client, permisos, prendido):
    llamadas = permisos(TESORERIA)
    tok, jti = sesion()
    r = client.post("/api/tesoreria/lotes/1/aprobar",
                    headers={"Authorization": f"Bearer {tok}", "X-2FA-Token": step_up(sid=jti)})
    assert r.status_code == 200
    reenviada = [c for c in llamadas.llamadas if c["metodo"] == "POST"][-1]
    assert not any(k.lower() == "x-2fa-token" for k in reenviada["headers"])


def test_el_token_de_step_up_se_reusa_mientras_dure(client, permisos, prendido):
    permisos(TESORERIA)
    tok, jti = sesion()
    h = {"Authorization": f"Bearer {tok}", "X-2FA-Token": step_up(sid=jti)}
    assert client.post("/api/tesoreria/lotes/1/aprobar", headers=h).status_code == 200
    assert client.post("/api/tesoreria/lotes/2/enviar", headers=h).status_code == 200


@pytest.mark.parametrize("caso", ["vencido", "otra_sesion", "otro_usuario", "otra_clave", "otro_scope",
                                  "es_la_sesion", "basura"])
def test_tokens_de_step_up_invalidos(client, permisos, prendido, caso):
    permisos(TESORERIA)
    tok, jti = sesion()
    su = {
        "vencido": lambda: step_up(sid=jti, minutos=-1),
        "otra_sesion": lambda: step_up(sid="otro-jti"),
        "otro_usuario": lambda: step_up(user_id=8, sid=jti),
        "otra_clave": lambda: step_up(sid=jti, clave=settings.jwt_secret),
        "otro_scope": lambda: step_up(sid=jti, scope="mfa_login"),
        "es_la_sesion": lambda: tok,
        "basura": lambda: "no-es-un-jwt",
    }[caso]()
    r = client.post("/api/tesoreria/lotes/1/aprobar", headers={"Authorization": f"Bearer {tok}", "X-2FA-Token": su})
    assert r.status_code == 403 and r.json()["code"] == "step_up_requerido"


def test_sin_2fa_y_politica_bloquear(client, permisos, prendido):
    permisos(TESORERIA)
    tok, _ = sesion(amr=("pwd",))
    r = client.post("/api/tesoreria/lotes/1/aprobar", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403 and r.json()["code"] == "2fa_requerido"


def test_sin_2fa_y_politica_permitir(client, permisos, prendido, monkeypatch):
    monkeypatch.setattr(settings, "tokenserver_stepup_sin_2fa", "permitir")
    permisos(TESORERIA)
    tok, _ = sesion(amr=None)
    assert client.post("/api/tesoreria/lotes/1/aprobar", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    # A quien SÍ tiene 2FA se le sigue pidiendo.
    tok, _ = sesion()
    assert client.post("/api/tesoreria/lotes/1/aprobar", headers={"Authorization": f"Bearer {tok}"}).status_code == 403


def test_el_permiso_se_controla_antes_que_el_step_up(client, permisos, prendido):
    permisos({"tesoreria": ["lotes:read"], "clientes": ["clients:read"]})
    tok, jti = sesion()
    r = client.post("/api/clientes/5/cbus", headers={"Authorization": f"Bearer {tok}", "X-2FA-Token": step_up(sid=jti)})
    assert r.status_code == 403 and r.json()["detail"] == "Acceso denegado"


def test_operaciones_no_sensibles_no_cambian(client, permisos, prendido):
    permisos(TESORERIA)
    tok, _ = sesion(amr=None)
    assert client.get("/api/tesoreria/lotes/1", headers={"Authorization": f"Bearer {tok}"}).status_code == 200


@pytest.mark.parametrize("ruta", ["/api/auth/2fa/login", "/api/auth/2fa/login/enrolar", "/api/auth/2fa/login/activar"])
def test_los_pasos_del_login_con_2fa_son_publicos(client, httpx_falso, ruta):
    r = client.post(ruta, json={"mfa_token": "x", "code": "123456"})
    assert r.status_code == 200
    assert httpx_falso.llamadas[-1]["url"] == f"{settings.security_service_url}{ruta}"


def test_el_step_up_y_el_estado_necesitan_sesion(client, httpx_falso):
    assert client.post("/api/auth/2fa/step-up", json={"code": "1"}).status_code == 401
    assert client.get("/api/auth/2fa/estado").status_code == 401
