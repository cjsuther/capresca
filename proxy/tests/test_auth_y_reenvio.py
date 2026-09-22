"""Gateway: validación del JWT, resolución de permisos, inyección de identidad y reenvío."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from jose import jwt

from app.config import settings
from app.middleware import auth as auth_mod
from tests.conftest import RespuestaFalsa, token_de



def test_health_no_pide_token(client):
    assert client.get("/health").json() == {"status": "ok", "service": "proxy"}


def test_login_es_publico_y_va_a_security(client, httpx_falso):
    r = client.post("/api/auth/login", json={"username": "ana", "password": "x"})
    assert r.status_code == 200
    assert httpx_falso.llamadas[-1]["url"] == f"{settings.security_service_url}/api/auth/login"


@pytest.mark.parametrize("headers,detalle", [
    ({}, "Token requerido"),
    ({"Authorization": "Basic YWRtaW46eA=="}, "Token requerido"),
    ({"Authorization": "Bearer no-es-un-jwt"}, "Token inválido o expirado"),
])
def test_sin_token_valido_no_se_pasa(client, headers, detalle):
    r = client.get("/api/clientes", headers=headers)
    assert r.status_code == 401 and r.json()["detail"] == detalle


def test_token_expirado_o_de_otro_secreto_se_rechaza(client):
    vencido = token_de(minutos=-1)
    assert client.get("/api/clientes", headers={"Authorization": f"Bearer {vencido}"}).status_code == 401
    ajeno = token_de(secreto="otro-secreto-distinto")
    assert client.get("/api/clientes", headers={"Authorization": f"Bearer {ajeno}"}).status_code == 401


def test_token_sin_firma_no_se_acepta(client):
    """alg=none: el payload es válido pero la firma no; jose debe rechazarlo."""
    sin_firma = jwt.encode({"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                           key="", algorithm="HS256")[: -10]
    assert client.get("/api/clientes", headers={"Authorization": f"Bearer {sin_firma}"}).status_code == 401


def test_falta_el_permiso_requerido(client, auth, permisos):
    permisos({"cajeros": ["rules:read"]})
    r = client.get("/api/clientes", headers=auth())
    assert r.status_code == 403
    assert r.json() == {"detail": "Acceso denegado", "required": "clientes:clients:read"}


def test_con_el_permiso_se_reenvia_con_la_identidad(client, auth, permisos):
    falso = permisos({"clientes": ["clients:read", "clients:write"], "cajeros": ["rules:read"]})
    r = client.get("/api/clientes?q=perez", headers=auth(user_id=42, username="ana"))
    assert r.status_code == 200
    reenvio = falso.llamadas[-1]
    assert reenvio["url"] == f"{settings.clientes_service_url}/api/clientes?q=perez"
    h = {k.lower(): v for k, v in reenvio["headers"].items()}
    assert h["x-user-id"] == "42" and h["x-username"] == "ana"
    assert h["x-user-permissions"] == "cajeros:rules:read,clientes:clients:read,clientes:clients:write"


def test_permiso_de_modulo_con_comodin(client, auth, permisos):
    """`creditos:*` = cualquier permiso del módulo; la autorización fina la hace el módulo."""
    permisos({"creditos": ["aprobaciones:aprobar"]})   # un aprobador sin creditos:read ve su bandeja
    assert client.get("/api/creditos/aprobaciones/inbox", headers=auth(user_id=1)).status_code == 200
    permisos({"cajeros": ["rules:read"]})   # otro usuario: la caché de permisos es por user_id
    assert client.get("/api/creditos/aprobaciones/inbox", headers=auth(user_id=2)).status_code == 403


def test_la_identidad_del_cliente_se_descarta(client, auth, permisos):
    """Suplantación: los X-User* que mande el cliente no deben llegar al módulo."""
    falso = permisos({"clientes": ["clients:read"]})
    client.get("/api/clientes", headers={**auth(user_id=42, username="ana"),
                                         "X-User-Id": "1", "X-Username": "admin",
                                         "X-User-Permissions": "security:users:write"})
    h = [(k.lower(), v) for k, v in falso.llamadas[-1]["headers"].items()]
    claves = [k for k, _ in h]
    assert claves.count("x-user-id") == 1 and claves.count("x-username") == 1
    d = dict(h)
    assert d["x-user-id"] == "42" and d["x-username"] == "ana"
    assert d["x-user-permissions"] == "clientes:clients:read"


def test_ruta_desconocida_es_404(client, auth, permisos):
    permisos({"clientes": ["clients:read"]})
    r = client.get("/api/no-existe", headers=auth())
    assert r.status_code == 404 and "Ruta no encontrada" in r.json()["detail"]


def test_si_security_no_responde_es_503(client, auth, httpx_falso):
    httpx_falso.error = httpx.RequestError("conexión rechazada")
    r = client.get("/api/clientes", headers=auth())
    assert r.status_code == 503 and r.json()["detail"] == "Servicio de seguridad no disponible"


def test_si_el_modulo_no_responde_es_502(client, auth, permisos, monkeypatch):
    falso = permisos({"clientes": ["clients:read"]})
    original = falso.request

    async def request_que_falla(self, *a, **kw):
        raise httpx.RequestError("sin ruta al host")

    monkeypatch.setattr(falso, "request", request_que_falla)
    r = client.get("/api/clientes", headers=auth())
    assert r.status_code == 502 and r.json()["detail"] == "Servicio no disponible"
    monkeypatch.setattr(falso, "request", original)


def test_los_permisos_se_cachean_por_usuario(client, auth, permisos):
    falso = permisos({"clientes": ["clients:read"]})
    client.get("/api/clientes", headers=auth(user_id=42))
    client.get("/api/clientes", headers=auth(user_id=42))
    consultas = [c for c in falso.llamadas if "/internal/permissions/" in c["url"]]
    assert len(consultas) == 1                      # la segunda salió de la caché
    client.get("/api/clientes", headers=auth(user_id=43))
    consultas = [c for c in falso.llamadas if "/internal/permissions/" in c["url"]]
    assert len(consultas) == 2                      # otro usuario, otra consulta


def test_se_reenvia_el_cuerpo_y_el_metodo(client, auth, permisos):
    falso = permisos({"clientes": ["clients:read", "clients:write"]})
    client.post("/api/clientes/human", headers=auth(), json={"apellido": "Perez"})
    envio = falso.llamadas[-1]
    assert envio["metodo"] == "POST" and b"Perez" in envio["body"]


def test_respuesta_binaria_pasa_sin_alterarse(client, auth, permisos):
    falso = permisos({"conciliacion": ["read", "download"]})
    pdf = b"%PDF-1.4 contenido binario \x00\x01"
    falso.respuesta_destino = RespuestaFalsa(200, None, content=pdf,
                                             headers={"content-type": "application/pdf"})
    r = client.get("/api/conciliacion/records/1/boleta", headers=auth())
    assert r.status_code == 200 and r.content == pdf
    assert r.headers["content-type"] == "application/pdf"


def test_el_estado_de_error_del_modulo_se_propaga(client, auth, permisos):
    falso = permisos({"clientes": ["clients:read"]})
    falso.respuesta_destino = RespuestaFalsa(404, None, content=b'{"detail":"no esta"}')
    r = client.get("/api/clientes/999", headers=auth())
    assert r.status_code == 404


def test_usuario_sin_permisos_no_entra_a_ningun_modulo(client, auth, permisos):
    permisos({})
    for ruta in ("/api/clientes", "/api/cajeros/rules", "/api/creditos/contratos/tablero"):
        assert client.get(ruta, headers=auth()).status_code == 403


def test_permisos_que_no_llegan_a_ser_dict_no_rompen(client, auth, httpx_falso):
    """Si security devuelve un status raro, el gateway responde 503 (no 500)."""
    httpx_falso.respuesta_permisos = RespuestaFalsa(500, None)
    assert client.get("/api/clientes", headers=auth()).status_code == 503
