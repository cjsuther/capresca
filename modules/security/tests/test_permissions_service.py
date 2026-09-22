"""Permisos efectivos (roles + overrides directos) y endpoints /internal/*."""
from app.services.auth_service import create_access_token, decode_token
from app.services.permissions_service import get_user_modules, get_user_permissions


# ── Cálculo de permisos efectivos ────────────────────────────────────


def test_usuario_inexistente_no_tiene_permisos(db):
    assert get_user_permissions(db, 9999) == {"modules": [], "actions": {}}


def test_usuario_inactivo_no_tiene_permisos(db, crear_usuario, crear_modulo, crear_permiso, crear_rol):
    user = crear_usuario(is_active=False)
    perm = crear_permiso(crear_modulo())
    user.roles = [crear_rol(permisos=[perm])]
    db.commit()
    assert get_user_permissions(db, user.id) == {"modules": [], "actions": {}}


def test_usuario_sin_roles_ni_overrides(db, crear_usuario):
    user = crear_usuario()
    assert get_user_permissions(db, user.id) == {"modules": [], "actions": {}}


def test_hereda_los_permisos_de_sus_roles(db, crear_usuario, crear_modulo, crear_permiso, crear_rol):
    user = crear_usuario()
    mod = crear_modulo(code="cajeros")
    leer = crear_permiso(mod, code="transactions:read")
    escribir = crear_permiso(mod, code="transactions:write")
    user.roles = [crear_rol(name="cajero", permisos=[leer, escribir])]
    db.commit()

    data = get_user_permissions(db, user.id)
    assert data["modules"] == ["cajeros"]
    assert sorted(data["actions"]["cajeros"]) == ["transactions:read", "transactions:write"]


def test_combina_varios_roles_y_ordena_los_modulos(
    db, crear_usuario, crear_modulo, crear_permiso, crear_rol
):
    user = crear_usuario()
    cajeros = crear_modulo(code="cajeros")
    clientes = crear_modulo(code="clientes", name="Clientes")
    p_cajeros = crear_permiso(cajeros, code="transactions:read")
    p_clientes = crear_permiso(clientes, code="clients:read")
    user.roles = [
        crear_rol(name="cajero", permisos=[p_cajeros]),
        crear_rol(name="atencion", permisos=[p_clientes]),
    ]
    db.commit()

    assert get_user_permissions(db, user.id)["modules"] == ["cajeros", "clientes"]


def test_un_rol_inactivo_no_aporta_permisos(db, crear_usuario, crear_modulo, crear_permiso, crear_rol):
    user = crear_usuario()
    perm = crear_permiso(crear_modulo())
    user.roles = [crear_rol(name="viejo", permisos=[perm], is_active=False)]
    db.commit()
    assert get_user_permissions(db, user.id) == {"modules": [], "actions": {}}


def test_un_modulo_inactivo_se_filtra_del_resultado(
    db, crear_usuario, crear_modulo, crear_permiso, crear_rol
):
    user = crear_usuario()
    vivo = crear_modulo(code="cajeros")
    apagado = crear_modulo(code="legacy", name="Legacy", is_active=False)
    user.roles = [crear_rol(permisos=[
        crear_permiso(vivo, code="transactions:read"),
        crear_permiso(apagado, code="interactions:read"),
    ])]
    db.commit()

    data = get_user_permissions(db, user.id)
    assert data["modules"] == ["cajeros"]
    assert "legacy" not in data["actions"]


def test_override_directo_granted_true_suma_un_permiso(
    db, crear_usuario, crear_modulo, crear_permiso, override_directo
):
    user = crear_usuario()
    perm = crear_permiso(crear_modulo(code="interbanking"), code="pagos:write")
    override_directo(user, perm, granted=True)
    db.refresh(user)

    assert get_user_permissions(db, user.id) == {
        "modules": ["interbanking"], "actions": {"interbanking": ["pagos:write"]}
    }


def test_override_directo_granted_false_revoca_un_permiso_del_rol(
    db, crear_usuario, crear_modulo, crear_permiso, crear_rol, override_directo
):
    user = crear_usuario()
    mod = crear_modulo(code="cajeros")
    leer = crear_permiso(mod, code="transactions:read")
    autorizar = crear_permiso(mod, code="transactions:authorize")
    user.roles = [crear_rol(permisos=[leer, autorizar])]
    db.commit()
    override_directo(user, autorizar, granted=False)
    db.refresh(user)

    data = get_user_permissions(db, user.id)
    assert data["actions"]["cajeros"] == ["transactions:read"]


def test_la_denegacion_directa_gana_sobre_la_concesion_directa(
    db, crear_usuario, crear_modulo, crear_permiso, override_directo
):
    """granted=False sobre el mismo permiso concedido por rol y por override: manda el deny."""
    user = crear_usuario()
    mod = crear_modulo(code="cajeros")
    unico = crear_permiso(mod, code="transactions:authorize")
    otro_mod = crear_modulo(code="clientes", name="Clientes")
    otro = crear_permiso(otro_mod, code="clients:read")
    override_directo(user, unico, granted=False)
    override_directo(user, otro, granted=True)
    db.refresh(user)

    data = get_user_permissions(db, user.id)
    assert data["modules"] == ["clientes"]


def test_denegar_todo_deja_el_payload_vacio(
    db, crear_usuario, crear_modulo, crear_permiso, crear_rol, override_directo
):
    user = crear_usuario()
    perm = crear_permiso(crear_modulo())
    user.roles = [crear_rol(permisos=[perm])]
    db.commit()
    override_directo(user, perm, granted=False)
    db.refresh(user)

    assert get_user_permissions(db, user.id) == {"modules": [], "actions": {}}


def test_get_user_modules_devuelve_solo_los_codigos(
    db, crear_usuario, crear_modulo, crear_permiso, crear_rol
):
    user = crear_usuario()
    user.roles = [crear_rol(permisos=[crear_permiso(crear_modulo(code="liquidaciones"), code="liq:read")])]
    db.commit()
    assert get_user_modules(db, user.id) == ["liquidaciones"]


# ── Endpoints internos ───────────────────────────────────────────────


def test_internal_permissions_devuelve_el_payload_efectivo(
    client, db, crear_usuario, crear_modulo, crear_permiso, crear_rol
):
    user = crear_usuario()
    user.roles = [crear_rol(permisos=[crear_permiso(crear_modulo(code="cajeros"), code="transactions:read")])]
    db.commit()

    r = client.get(f"/internal/permissions/{user.id}")
    assert r.status_code == 200
    assert r.json() == {"modules": ["cajeros"], "actions": {"cajeros": ["transactions:read"]}}


def test_internal_permissions_de_usuario_inexistente_devuelve_200_vacio(client):
    """No es 404: el proxy espera siempre un payload (usuario sin permisos)."""
    r = client.get("/internal/permissions/12345")
    assert r.status_code == 200 and r.json() == {"modules": [], "actions": {}}


def test_internal_permissions_con_id_no_numerico_da_422(client):
    assert client.get("/internal/permissions/abc").status_code == 422


def test_internal_modules_devuelve_la_lista_de_modulos(
    client, db, crear_usuario, crear_modulo, crear_permiso, crear_rol
):
    user = crear_usuario()
    user.roles = [crear_rol(permisos=[crear_permiso(crear_modulo(code="clientes"), code="clients:read")])]
    db.commit()

    r = client.get(f"/internal/modules/{user.id}")
    assert r.status_code == 200 and r.json() == {"modules": ["clientes"]}


def test_internal_modules_sin_permisos_devuelve_lista_vacia(client, crear_usuario):
    user = crear_usuario()
    assert client.get(f"/internal/modules/{user.id}").json() == {"modules": []}


# ── /internal/validate-token ─────────────────────────────────────────


def test_validate_token_ok(client, crear_usuario):
    user = crear_usuario()
    token = create_access_token(user.id, user.username)
    r = client.get("/internal/validate-token", params={"token": token})
    assert r.status_code == 200
    assert r.json() == {
        "valid": True, "user_id": user.id, "username": user.username,
        "exp": decode_token(token)["exp"],
    }


def test_validate_token_invalido_da_401(client):
    r = client.get("/internal/validate-token", params={"token": "basura"})
    assert r.status_code == 401 and r.json()["detail"] == "Token inválido o expirado"


def test_validate_token_revocado_da_401(client, crear_usuario):
    user = crear_usuario()
    token = create_access_token(user.id, user.username)
    client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    r = client.get("/internal/validate-token", params={"token": token})
    assert r.status_code == 401 and r.json()["detail"] == "Token revocado"


def test_validate_token_sin_query_param_da_422(client):
    assert client.get("/internal/validate-token").status_code == 422
