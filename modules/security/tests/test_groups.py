"""Grupos de usuarios: ABM, integrantes, roles del grupo y su efecto en los permisos efectivos."""
from app.models.group import Group
from app.services.permissions_service import get_user_permissions

BASE = "/api/security/groups"


def _grupo(db, name="tesoreria", roles=(), users=(), is_active=True):
    g = Group(name=name, description="Área", is_active=is_active)
    g.roles = list(roles)
    g.users = list(users)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


# ── ABM ──────────────────────────────────────────────────────────────


def test_alta_de_grupo(client, db):
    r = client.post(BASE, json={"name": "Tesorería", "description": "Área de pagos"})
    assert r.status_code == 201
    assert r.json() | {"id": 0} == {"id": 0, "name": "Tesorería", "description": "Área de pagos",
                                     "is_active": True, "roles": [], "users": []}
    assert db.query(Group).filter_by(name="Tesorería").one()


def test_nombre_repetido_da_400_en_alta_y_en_modificacion(client, db):
    _grupo(db, "Área A")
    b = _grupo(db, "Área B")
    assert client.post(BASE, json={"name": "Área A"}).json()["detail"] == "El nombre de grupo ya existe"
    assert client.put(f"{BASE}/{b.id}", json={"name": "Área A"}).status_code == 400
    assert client.put(f"{BASE}/{b.id}", json={"name": "Área B", "description": "otra"}).status_code == 200


def test_listado_ordenado_con_integrantes_y_roles(client, db, crear_usuario, crear_rol):
    ana = crear_usuario("ana")
    _grupo(db, "zeta")
    _grupo(db, "alfa", roles=[crear_rol("cajero")], users=[ana])
    body = client.get(BASE).json()
    assert [g["name"] for g in body] == ["alfa", "zeta"]
    assert body[0]["roles"] == [{"id": body[0]["roles"][0]["id"], "name": "cajero"}]
    assert [u["username"] for u in body[0]["users"]] == ["ana"]


def test_baja_de_grupo_no_borra_usuarios_ni_roles(client, db, crear_usuario, crear_rol):
    ana, rol = crear_usuario("ana"), crear_rol("cajero")
    g = _grupo(db, roles=[rol], users=[ana])
    assert client.delete(f"{BASE}/{g.id}").status_code == 204
    db.expire_all()
    assert db.query(Group).count() == 0
    assert ana.groups == [] and rol.name == "cajero"


def test_grupo_inexistente_da_404(client):
    assert client.put(f"{BASE}/999", json={"name": "x1"}).status_code == 404
    assert client.delete(f"{BASE}/999").status_code == 404
    assert client.post(f"{BASE}/999/users", json={"user_ids": []}).status_code == 404


# ── Integrantes y roles ──────────────────────────────────────────────


def test_asignar_integrantes_y_roles_reemplaza_el_conjunto(client, db, crear_usuario, crear_rol):
    ana, beto = crear_usuario("ana"), crear_usuario("beto")
    r1, r2 = crear_rol("cajero"), crear_rol("supervisor")
    g = _grupo(db, users=[ana], roles=[r1])

    r = client.post(f"{BASE}/{g.id}/users", json={"user_ids": [beto.id]})
    assert [u["username"] for u in r.json()["users"]] == ["beto"]
    r = client.post(f"{BASE}/{g.id}/roles", json={"role_ids": [r2.id, r1.id]})
    assert [x["name"] for x in r.json()["roles"]] == ["cajero", "supervisor"]


def test_ids_inexistentes_dan_400_sin_cambiar_nada(client, db, crear_usuario, crear_rol):
    ana = crear_usuario("ana")
    g = _grupo(db, users=[ana])
    assert client.post(f"{BASE}/{g.id}/users", json={"user_ids": [ana.id, 999]}).status_code == 400
    assert client.post(f"{BASE}/{g.id}/roles", json={"role_ids": [999]}).status_code == 400
    db.expire_all()
    assert [u.username for u in g.users] == ["ana"]


def test_desde_el_usuario_se_eligen_sus_grupos(client, db, crear_usuario, crear_rol):
    ana = crear_usuario("ana")
    g = _grupo(db, "tesoreria", roles=[crear_rol("tesorero")])
    r = client.post(f"/api/security/users/{ana.id}/groups", json={"group_ids": [g.id]})
    assert r.status_code == 200
    assert r.json()["groups"][0]["name"] == "tesoreria"
    assert r.json()["groups"][0]["roles"][0]["name"] == "tesorero"
    assert r.json()["roles"] == []          # el rol es heredado, no propio
    assert client.post(f"/api/security/users/{ana.id}/groups", json={"group_ids": [999]}).status_code == 400


# ── Permisos efectivos ───────────────────────────────────────────────


def test_el_integrante_hereda_los_permisos_de_los_roles_del_grupo(
        db, crear_usuario, crear_rol, crear_modulo, crear_permiso):
    mod = crear_modulo("tesoreria", "Tesorería")
    ver, aprobar = crear_permiso(mod, "lotes:read"), crear_permiso(mod, "aprobaciones:aprobar")
    ana = crear_usuario("ana")
    ana.roles = [crear_rol("lector", permisos=[ver])]
    _grupo(db, roles=[crear_rol("tesorero", permisos=[aprobar])], users=[ana])

    assert sorted(get_user_permissions(db, ana.id)["actions"]["tesoreria"]) == ["aprobaciones:aprobar", "lotes:read"]


def test_grupo_inactivo_o_rol_inactivo_no_da_permisos(db, crear_usuario, crear_rol, crear_modulo, crear_permiso):
    mod = crear_modulo("tesoreria", "Tesorería")
    ver = crear_permiso(mod, "lotes:read")
    ana, beto = crear_usuario("ana"), crear_usuario("beto")
    _grupo(db, "apagado", roles=[crear_rol("r1", permisos=[ver])], users=[ana], is_active=False)
    _grupo(db, "rol-apagado", roles=[crear_rol("r2", permisos=[ver], is_active=False)], users=[beto])

    assert get_user_permissions(db, ana.id) == {"modules": [], "actions": {}}
    assert get_user_permissions(db, beto.id) == {"modules": [], "actions": {}}


def test_el_override_directo_deniega_aunque_venga_por_grupo(
        db, crear_usuario, crear_rol, crear_modulo, crear_permiso, override_directo):
    mod = crear_modulo("tesoreria", "Tesorería")
    ver = crear_permiso(mod, "lotes:read")
    ana = crear_usuario("ana")
    _grupo(db, roles=[crear_rol("r1", permisos=[ver])], users=[ana])
    override_directo(ana, ver, granted=False)
    assert get_user_permissions(db, ana.id)["actions"] == {}


def test_sacar_al_usuario_del_grupo_le_quita_lo_heredado(
        client, db, crear_usuario, crear_rol, crear_modulo, crear_permiso):
    mod = crear_modulo("tesoreria", "Tesorería")
    ana = crear_usuario("ana")
    g = _grupo(db, roles=[crear_rol("r1", permisos=[crear_permiso(mod, "lotes:read")])], users=[ana])
    assert client.get(f"/api/security/users/{ana.id}/effective-permissions").json()["modules"] == ["tesoreria"]
    client.post(f"{BASE}/{g.id}/users", json={"user_ids": []})
    db.expire_all()
    assert client.get(f"/api/security/users/{ana.id}/effective-permissions").json() == {"modules": [], "actions": {}}
    assert client.get("/api/security/users/999/effective-permissions").status_code == 404
