"""ABM de usuarios, asignación de roles y cambios de contraseña."""
from app.models.user import User
from app.services.auth_service import verify_password

BASE = "/api/security/users"


def _alta(client, username="mlopez", email=None, password="Secreta123!"):
    return client.post(BASE, json={
        "username": username,
        "email": email or f"{username}@sistema.local",
        "password": password,
        "full_name": "María López",
    })


# ── Listado ──────────────────────────────────────────────────────────


def test_listado_vacio(client):
    assert client.get(BASE).json() == {"data": [], "total": 0, "page": 1, "per_page": 20}


def test_listado_pagina_y_conserva_el_total(client, crear_usuario):
    for i in range(5):
        crear_usuario(username=f"u{i}")

    r = client.get(BASE, params={"page": 2, "per_page": 2}).json()
    assert r["total"] == 5 and r["page"] == 2 and len(r["data"]) == 2
    assert [u["username"] for u in r["data"]] == ["u2", "u3"]


def test_listado_no_expone_el_hash(client, crear_usuario):
    crear_usuario()
    assert "hashed_password" not in client.get(BASE).json()["data"][0]


def test_listado_valida_los_parametros_de_paginado(client):
    assert client.get(BASE, params={"page": 0}).status_code == 422
    assert client.get(BASE, params={"per_page": 501}).status_code == 422


# ── Alta ─────────────────────────────────────────────────────────────


def test_alta_crea_el_usuario_activo_y_hashea_la_contraseña(client, db):
    r = _alta(client)
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == "mlopez" and body["is_active"] is True and body["roles"] == []

    guardado = db.query(User).filter_by(username="mlopez").one()
    assert guardado.hashed_password != "Secreta123!"
    assert verify_password("Secreta123!", guardado.hashed_password)


def test_alta_con_username_repetido_da_400(client, crear_usuario):
    crear_usuario(username="mlopez", email="otro@sistema.local")
    r = _alta(client, username="mlopez")
    assert r.status_code == 400 and r.json()["detail"] == "El username ya existe"


def test_alta_con_email_repetido_da_400(client, crear_usuario):
    crear_usuario(username="otro", email="mlopez@sistema.local")
    r = _alta(client, username="mlopez")
    assert r.status_code == 400 and r.json()["detail"] == "El email ya existe"


def test_alta_sin_campos_obligatorios_da_422(client):
    assert client.post(BASE, json={"username": "x"}).status_code == 422


def test_alta_acepta_un_email_con_formato_invalido(client):
    """TODO(bug): UserCreate.email es `str` pelado (app/schemas/user.py:8), no EmailStr:
    no hay validación de formato de email en el alta."""
    assert _alta(client, username="raro", email="no-es-un-email").status_code == 201


# ── Detalle ──────────────────────────────────────────────────────────


def test_detalle_devuelve_el_usuario(client, crear_usuario):
    user = crear_usuario()
    assert client.get(f"{BASE}/{user.id}").json()["username"] == user.username


def test_detalle_de_usuario_inexistente_da_404(client):
    r = client.get(f"{BASE}/999")
    assert r.status_code == 404 and r.json()["detail"] == "Usuario no encontrado"


# ── Modificación ─────────────────────────────────────────────────────


def test_modificacion_parcial_actualiza_solo_lo_enviado(client, crear_usuario):
    user = crear_usuario(full_name="Juan Pérez")
    r = client.put(f"{BASE}/{user.id}", json={"email": "nuevo@sistema.local"})
    assert r.status_code == 200
    assert r.json()["email"] == "nuevo@sistema.local" and r.json()["full_name"] == "Juan Pérez"


def test_modificacion_puede_desactivar_al_usuario(client, crear_usuario):
    user = crear_usuario()
    assert client.put(f"{BASE}/{user.id}", json={"is_active": False}).json()["is_active"] is False


def test_modificacion_ignora_los_nulos(client, crear_usuario):
    """TODO(bug): update_user usa exclude_none (app/services/user_service.py:43): mandar
    full_name=null NO limpia el campo, se descarta silenciosamente."""
    user = crear_usuario(full_name="Juan Pérez")
    assert client.put(f"{BASE}/{user.id}", json={"full_name": None}).json()["full_name"] == "Juan Pérez"


def test_modificacion_de_usuario_inexistente_da_404(client):
    assert client.put(f"{BASE}/999", json={"email": "x@y.com"}).status_code == 404


# ── Baja lógica ──────────────────────────────────────────────────────


def test_baja_es_logica_y_bloquea_el_login(client, db, crear_usuario):
    user = crear_usuario(username="jperez", password="Secreta123!")
    r = client.delete(f"{BASE}/{user.id}")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert db.query(User).filter_by(id=user.id).first() is not None  # no se borra la fila

    login = client.post("/api/auth/login", json={"username": "jperez", "password": "Secreta123!"})
    assert login.status_code == 401


def test_baja_de_usuario_inexistente_da_404(client):
    assert client.delete(f"{BASE}/999").status_code == 404


# ── Asignación de roles ──────────────────────────────────────────────


def test_asignar_roles_reemplaza_el_conjunto(client, db, crear_usuario, crear_rol):
    user = crear_usuario()
    cajero = crear_rol(name="cajero")
    supervisor = crear_rol(name="supervisor")
    user.roles = [cajero]
    db.commit()

    r = client.post(f"{BASE}/{user.id}/roles", json={"role_ids": [supervisor.id]})
    assert r.status_code == 200
    assert [rol["name"] for rol in r.json()["roles"]] == ["supervisor"]


def test_asignar_lista_vacia_saca_todos_los_roles(client, db, crear_usuario, crear_rol):
    user = crear_usuario()
    user.roles = [crear_rol(name="cajero")]
    db.commit()
    assert client.post(f"{BASE}/{user.id}/roles", json={"role_ids": []}).json()["roles"] == []


def test_asignar_un_rol_inexistente_da_400(client, crear_usuario):
    user = crear_usuario()
    r = client.post(f"{BASE}/{user.id}/roles", json={"role_ids": [404]})
    assert r.status_code == 400 and r.json()["detail"] == "Uno o más roles no encontrados"


def test_asignar_roles_a_usuario_inexistente_da_404(client):
    assert client.post(f"{BASE}/999/roles", json={"role_ids": []}).status_code == 404


def test_asignar_roles_repetidos_da_400(client, crear_usuario, crear_rol):
    """TODO(bug): assign_roles compara len(roles) != len(role_ids) (user_service.py:75):
    con ids duplicados el conteo no coincide y rechaza un pedido válido."""
    user = crear_usuario()
    rol = crear_rol(name="cajero")
    r = client.post(f"{BASE}/{user.id}/roles", json={"role_ids": [rol.id, rol.id]})
    assert r.status_code == 400


# ── Contraseña: cambio por admin ─────────────────────────────────────


def test_admin_cambia_la_contraseña(client, db, crear_usuario):
    user = crear_usuario(username="jperez", password="Vieja123!")
    r = client.put(f"{BASE}/{user.id}/password", json={"new_password": "Nueva123!"})
    assert r.status_code == 204

    db.refresh(user)
    assert verify_password("Nueva123!", user.hashed_password)
    assert client.post("/api/auth/login",
                       json={"username": "jperez", "password": "Nueva123!"}).status_code == 200


def test_admin_cambia_la_contraseña_de_usuario_inexistente_da_404(client):
    assert client.put(f"{BASE}/999/password", json={"new_password": "Nueva123!"}).status_code == 404


def test_la_contraseña_tiene_largo_minimo(client, crear_usuario):
    """Antes se aceptaba una contraseña vacía (sin min_length en el schema)."""
    user = crear_usuario()
    assert client.put(f"{BASE}/{user.id}/password", json={"new_password": ""}).status_code == 422
    assert client.put(f"{BASE}/{user.id}/password", json={"new_password": "corta1"}).status_code == 422
    assert client.put(f"{BASE}/{user.id}/password", json={"new_password": "Larga123!"}).status_code == 204
    assert client.post(BASE, json={"username": "nuevo", "email": "n@x.com",
                                   "password": "corta"}).status_code == 422


# ── Contraseña: cambio propio ────────────────────────────────────────


def test_el_usuario_cambia_su_propia_contraseña(client, crear_usuario, db):
    """La ruta literal /me/password va declarada ANTES que la paramétrica /{user_id}/password;
    si no, "me" se parsea como id y el endpoint propio queda inalcanzable (422)."""
    user = crear_usuario(password="Secreta123!")
    h = {"X-User-Id": str(user.id)}
    r = client.put(f"{BASE}/me/password",
                   json={"current_password": "Secreta123!", "new_password": "Nueva123!"}, headers=h)
    assert r.status_code == 204
    db.refresh(user)
    assert verify_password("Nueva123!", user.hashed_password)

    # con la contraseña actual equivocada, no cambia
    assert client.put(f"{BASE}/me/password",
                      json={"current_password": "otra", "new_password": "Otra1234!"},
                      headers=h).status_code == 400
    # sin identidad del gateway, tampoco
    assert client.put(f"{BASE}/me/password",
                      json={"current_password": "Nueva123!", "new_password": "Otra1234!"}).status_code == 401


def test_cambio_propio_de_contraseña_a_nivel_servicio(db, crear_usuario):
    """La lógica sí funciona; se ejercita directo porque la ruta está tapada (ver test previo)."""
    from app.services.user_service import change_own_password

    user = crear_usuario(password="Vieja123!")
    change_own_password(db, user.id, "Vieja123!", "Nueva123!")
    db.refresh(user)
    assert verify_password("Nueva123!", user.hashed_password)


def test_cambio_propio_con_contraseña_actual_incorrecta_da_400(db, crear_usuario):
    import pytest
    from fastapi import HTTPException
    from app.services.user_service import change_own_password

    user = crear_usuario(password="Vieja123!")
    with pytest.raises(HTTPException) as exc:
        change_own_password(db, user.id, "mala", "Nueva123!")
    assert exc.value.status_code == 400
    assert exc.value.detail == "La contraseña actual es incorrecta"
