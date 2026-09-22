"""Login, logout, refresh, hash de contraseñas y ciclo de vida del JWT."""
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import settings
from app.models.permission import TokenBlacklist
from app.services import auth_service


# ── Hash y verificación de contraseñas ───────────────────────────────


def test_hash_no_guarda_la_contraseña_en_claro():
    hashed = auth_service.hash_password("Secreta123!")
    assert hashed != "Secreta123!"
    assert hashed.startswith("$2")  # bcrypt


def test_verify_password_distingue_correcta_de_incorrecta():
    hashed = auth_service.hash_password("Secreta123!")
    assert auth_service.verify_password("Secreta123!", hashed) is True
    assert auth_service.verify_password("otra", hashed) is False


def test_dos_hashes_de_la_misma_contraseña_difieren_por_el_salt():
    assert auth_service.hash_password("igual") != auth_service.hash_password("igual")


# ── Emisión y decodificación del token ───────────────────────────────


def test_el_token_lleva_sub_username_jti_y_exp():
    token = auth_service.create_access_token(42, "jperez")
    payload = auth_service.decode_token(token)
    assert payload["sub"] == "42"  # el sub siempre viaja como string
    assert payload["username"] == "jperez"
    assert payload["jti"] and payload["exp"] > payload["iat"]


def test_cada_token_tiene_un_jti_distinto():
    uno = auth_service.decode_token(auth_service.create_access_token(1, "a"))
    otro = auth_service.decode_token(auth_service.create_access_token(1, "a"))
    assert uno["jti"] != otro["jti"]


def test_la_expiracion_respeta_jwt_expire_hours():
    payload = auth_service.decode_token(auth_service.create_access_token(1, "a"))
    horas = (payload["exp"] - payload["iat"]) / 3600
    assert horas == pytest.approx(settings.jwt_expire_hours, abs=0.01)


def test_decode_token_rechaza_basura():
    assert auth_service.decode_token("no-es-un-jwt") is None


def test_decode_token_rechaza_firma_de_otro_secreto():
    ajeno = jwt.encode({"sub": "1", "username": "a"}, "otro-secreto", algorithm="HS256")
    assert auth_service.decode_token(ajeno) is None


def test_decode_token_rechaza_token_expirado():
    vencido = jwt.encode(
        {"sub": "1", "username": "a", "jti": "x",
         "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )
    assert auth_service.decode_token(vencido) is None


# ── authenticate_user ────────────────────────────────────────────────


def test_authenticate_user_ok(db, crear_usuario):
    user = crear_usuario(username="jperez", password="Secreta123!")
    assert auth_service.authenticate_user(db, "jperez", "Secreta123!").id == user.id


def test_authenticate_user_con_password_incorrecta(db, crear_usuario):
    crear_usuario(username="jperez", password="Secreta123!")
    assert auth_service.authenticate_user(db, "jperez", "mala") is None


def test_authenticate_user_con_usuario_inexistente(db):
    assert auth_service.authenticate_user(db, "nadie", "x") is None


def test_authenticate_user_ignora_usuarios_inactivos(db, crear_usuario):
    crear_usuario(username="baja", password="Secreta123!", is_active=False)
    assert auth_service.authenticate_user(db, "baja", "Secreta123!") is None


# ── POST /api/auth/login ─────────────────────────────────────────────


def _login(client, username="jperez", password="Secreta123!"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_devuelve_token_datos_del_usuario_y_permisos(
    client, crear_usuario, crear_modulo, crear_permiso, crear_rol, db
):
    user = crear_usuario(username="jperez", password="Secreta123!")
    mod = crear_modulo(code="cajeros")
    perm = crear_permiso(mod, code="transactions:read")
    user.roles = [crear_rol(name="cajero", permisos=[perm])]
    db.commit()

    r = _login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"] == {"id": user.id, "username": "jperez", "full_name": "Juan Pérez"}
    assert body["permissions"] == {"modules": ["cajeros"], "actions": {"cajeros": ["transactions:read"]}}
    assert auth_service.decode_token(body["access_token"])["sub"] == str(user.id)


def test_login_sin_permisos_devuelve_payload_vacio(client, crear_usuario):
    crear_usuario(username="jperez", password="Secreta123!")
    assert _login(client).json()["permissions"] == {"modules": [], "actions": {}}


def test_login_con_credenciales_invalidas_da_401(client, crear_usuario):
    crear_usuario(username="jperez", password="Secreta123!")
    r = _login(client, password="mala")
    assert r.status_code == 401 and r.json()["detail"] == "Credenciales inválidas"


def test_login_de_usuario_inactivo_da_401(client, crear_usuario):
    crear_usuario(username="baja", password="Secreta123!", is_active=False)
    assert _login(client, username="baja").status_code == 401


def test_login_sin_password_da_422(client):
    assert client.post("/api/auth/login", json={"username": "jperez"}).status_code == 422


# ── POST /api/auth/logout ────────────────────────────────────────────


def test_logout_agrega_el_jti_a_la_blacklist(client, db, crear_usuario):
    user = crear_usuario()
    token = auth_service.create_access_token(user.id, user.username)
    jti = auth_service.decode_token(token)["jti"]

    r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json() == {"message": "Sesión cerrada exitosamente"}
    assert db.query(TokenBlacklist).filter_by(jti=jti).first() is not None


def test_logout_repetido_no_duplica_la_entrada(client, db, crear_usuario):
    user = crear_usuario()
    token = auth_service.create_access_token(user.id, user.username)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/auth/logout", headers=headers)
    client.post("/api/auth/logout", headers=headers)
    assert db.query(TokenBlacklist).count() == 1


def test_logout_sin_header_da_401(client):
    r = client.post("/api/auth/logout")
    assert r.status_code == 401 and r.json()["detail"] == "Token requerido"


def test_logout_con_esquema_distinto_de_bearer_da_401(client):
    assert client.post("/api/auth/logout", headers={"Authorization": "Basic abc"}).status_code == 401


def test_logout_con_token_invalido_da_401(client):
    r = client.post("/api/auth/logout", headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401 and r.json()["detail"] == "Token inválido"


def test_logout_sin_exp_usa_el_momento_actual(client, db):
    """Un token sin exp igual se revoca (rama del `if exp` en auth.py)."""
    token = jwt.encode({"sub": "5", "username": "a", "jti": "sin-exp"},
                       settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    assert db.query(TokenBlacklist).filter_by(jti="sin-exp").first() is not None


# ── POST /api/auth/refresh ───────────────────────────────────────────


def test_refresh_emite_un_token_nuevo(client, crear_usuario):
    user = crear_usuario()
    token = auth_service.create_access_token(user.id, user.username)
    r = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["token_type"] == "bearer"

    nuevo = auth_service.decode_token(r.json()["access_token"])
    viejo = auth_service.decode_token(token)
    assert nuevo["sub"] == viejo["sub"] and nuevo["jti"] != viejo["jti"]


def test_refresh_con_token_revocado_da_401(client, crear_usuario):
    user = crear_usuario()
    token = auth_service.create_access_token(user.id, user.username)
    headers = {"Authorization": f"Bearer {token}"}
    client.post("/api/auth/logout", headers=headers)

    r = client.post("/api/auth/refresh", headers=headers)
    assert r.status_code == 401 and r.json()["detail"] == "Token revocado"


def test_refresh_sin_header_da_401(client):
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_con_token_expirado_da_401(client):
    vencido = jwt.encode(
        {"sub": "1", "username": "a", "jti": "x",
         "exp": datetime.now(timezone.utc) - timedelta(seconds=5)},
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )
    r = client.post("/api/auth/refresh", headers={"Authorization": f"Bearer {vencido}"})
    assert r.status_code == 401 and r.json()["detail"] == "Token inválido o expirado"


# ── Blacklist a nivel servicio ───────────────────────────────────────


def test_is_token_blacklisted(db):
    assert auth_service.is_token_blacklisted(db, "abc") is False
    auth_service.blacklist_token(db, "abc", 1, datetime.now(timezone.utc) + timedelta(hours=1))
    assert auth_service.is_token_blacklisted(db, "abc") is True


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "security"}
