"""ABM de roles y asignación de permisos, más los listados de módulos y permisos."""
from app.models.role import Role

BASE = "/api/security/roles"


# ── ABM de roles ─────────────────────────────────────────────────────


def test_listado_de_roles_incluye_los_inactivos(client, crear_rol):
    crear_rol(name="cajero")
    crear_rol(name="viejo", is_active=False)
    nombres = sorted(r["name"] for r in client.get(BASE).json())
    assert nombres == ["cajero", "viejo"]


def test_alta_de_rol(client, db):
    r = client.post(BASE, json={"name": "auditor", "description": "Sólo lectura"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "auditor" and body["is_active"] is True and body["permissions"] == []
    assert db.query(Role).filter_by(name="auditor").first() is not None


def test_alta_de_rol_con_nombre_repetido_da_400(client, crear_rol):
    crear_rol(name="auditor")
    r = client.post(BASE, json={"name": "auditor"})
    assert r.status_code == 400 and r.json()["detail"] == "El nombre de rol ya existe"


def test_alta_de_rol_sin_nombre_da_422(client):
    assert client.post(BASE, json={"description": "sin nombre"}).status_code == 422


def test_modificacion_de_rol(client, crear_rol):
    rol = crear_rol(name="auditor")
    r = client.put(f"{BASE}/{rol.id}", json={"description": "Nueva descripción", "is_active": False})
    assert r.status_code == 200
    assert r.json()["description"] == "Nueva descripción" and r.json()["is_active"] is False
    assert r.json()["name"] == "auditor"  # lo no enviado no cambia


def test_modificacion_de_rol_inexistente_da_404(client):
    r = client.put(f"{BASE}/999", json={"name": "x"})
    assert r.status_code == 404 and r.json()["detail"] == "Rol no encontrado"


def test_baja_de_rol_lo_elimina_y_lo_saca_de_los_usuarios(
    client, db, crear_rol, crear_usuario
):
    user = crear_usuario()
    rol = crear_rol(name="temporal")
    user.roles = [rol]
    db.commit()

    assert client.delete(f"{BASE}/{rol.id}").status_code == 204
    db.expire_all()
    assert db.query(Role).filter_by(id=rol.id).first() is None
    assert user.roles == []


def test_baja_de_rol_inexistente_da_404(client):
    assert client.delete(f"{BASE}/999").status_code == 404


# ── Asignación de permisos a un rol ──────────────────────────────────


def test_asignar_permisos_reemplaza_el_conjunto(client, db, crear_rol, crear_modulo, crear_permiso):
    mod = crear_modulo()
    leer = crear_permiso(mod, code="transactions:read")
    escribir = crear_permiso(mod, code="transactions:write")
    rol = crear_rol(name="cajero", permisos=[leer])

    r = client.post(f"{BASE}/{rol.id}/permissions", json={"permission_ids": [escribir.id]})
    assert r.status_code == 200
    assert [p["code"] for p in r.json()["permissions"]] == ["transactions:write"]


def test_asignar_lista_vacia_saca_todos_los_permisos(client, crear_rol, crear_modulo, crear_permiso):
    rol = crear_rol(name="cajero", permisos=[crear_permiso(crear_modulo())])
    assert client.post(f"{BASE}/{rol.id}/permissions", json={"permission_ids": []}).json()["permissions"] == []


def test_asignar_un_permiso_inexistente_da_400(client, crear_rol):
    rol = crear_rol(name="cajero")
    r = client.post(f"{BASE}/{rol.id}/permissions", json={"permission_ids": [404]})
    assert r.status_code == 400 and r.json()["detail"] == "Uno o más permisos no encontrados"


def test_asignar_permisos_a_un_rol_inexistente_da_404(client):
    assert client.post(f"{BASE}/999/permissions", json={"permission_ids": []}).status_code == 404


def test_asignar_permisos_con_payload_invalido_da_422(client, crear_rol):
    rol = crear_rol(name="cajero")
    assert client.post(f"{BASE}/{rol.id}/permissions", json={"permission_ids": "todos"}).status_code == 422


def test_los_permisos_del_rol_impactan_en_el_payload_de_login(
    client, db, crear_rol, crear_usuario, crear_modulo, crear_permiso
):
    """Recorrido completo: alta de rol → permisos → usuario → login."""
    user = crear_usuario(username="jperez", password="Secreta123!")
    perm = crear_permiso(crear_modulo(code="clientes", name="Clientes"), code="clients:read")
    rol = crear_rol(name="atencion")
    client.post(f"{BASE}/{rol.id}/permissions", json={"permission_ids": [perm.id]})
    client.post(f"/api/security/users/{user.id}/roles", json={"role_ids": [rol.id]})

    body = client.post("/api/auth/login",
                       json={"username": "jperez", "password": "Secreta123!"}).json()
    assert body["permissions"] == {"modules": ["clientes"], "actions": {"clientes": ["clients:read"]}}


# ── Listado de módulos ───────────────────────────────────────────────


def test_listado_de_modulos_solo_devuelve_los_activos(client, crear_modulo):
    crear_modulo(code="cajeros", name="Cajeros")
    crear_modulo(code="legacy", name="Legacy", is_active=False)

    r = client.get("/api/security/modules")
    assert r.status_code == 200
    assert [m["code"] for m in r.json()] == ["cajeros"]


def test_listado_de_modulos_vacio(client):
    assert client.get("/api/security/modules").json() == []


# ── Listado de permisos ──────────────────────────────────────────────


def test_listado_de_permisos_ordena_por_modulo_y_codigo(client, crear_modulo, crear_permiso):
    cajeros = crear_modulo(code="cajeros")
    clientes = crear_modulo(code="clientes", name="Clientes")
    crear_permiso(clientes, code="clients:read")
    crear_permiso(cajeros, code="transactions:write")
    crear_permiso(cajeros, code="rules:read")

    codigos = [p["code"] for p in client.get("/api/security/permissions").json()]
    assert codigos == ["rules:read", "transactions:write", "clients:read"]


def test_listado_de_permisos_incluye_los_de_modulos_inactivos(client, crear_modulo, crear_permiso):
    """El ABM muestra todo; el filtro por módulo activo es del cálculo de permisos efectivos."""
    apagado = crear_modulo(code="legacy", name="Legacy", is_active=False)
    crear_permiso(apagado, code="interactions:read")
    assert len(client.get("/api/security/permissions").json()) == 1
