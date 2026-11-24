"""Listado paginado y filtrado de usuarios (GET /users/search) para la pantalla de Seguridad."""
import pytest

from app.models.group import Group

URL = "/api/security/users/search"
BASE = "/api/security/users"


def _nombres(r):
    assert r.status_code == 200, r.text
    return [u["username"] for u in r.json()["items"]]


@pytest.fixture
def grupo(db):
    def _crear(name, roles=(), users=(), is_active=True):
        g = Group(name=name, is_active=is_active)
        g.roles = list(roles)
        g.users = list(users)
        db.add(g)
        db.commit()
        return g
    return _crear


# ── Paginado ─────────────────────────────────────────────────────────


def test_vacio(client):
    assert client.get(URL).json() == {"items": [], "total": 0, "page": 1, "page_size": 25, "pages": 1}


def test_pagina_por_defecto_de_25_y_devuelve_el_total(client, crear_usuario):
    for i in range(30):
        crear_usuario(username=f"u{i:02d}", full_name=None)
    r = client.get(URL).json()
    assert r["total"] == 30 and r["pages"] == 2 and len(r["items"]) == 25

    assert _nombres(client.get(URL, params={"page": 2})) == [f"u{i}" for i in range(25, 30)]


def test_valida_page_size_maximo_100_y_parametros(client):
    assert client.get(URL, params={"page_size": 100}).status_code == 200
    assert client.get(URL, params={"page_size": 101}).status_code == 422
    assert client.get(URL, params={"page": 0}).status_code == 422
    assert client.get(URL, params={"sort": "hashed_password"}).status_code == 422
    assert client.get(URL, params={"estado": "bloqueado"}).status_code == 422
    assert client.get(URL, params={"order": "up"}).status_code == 422


def test_no_expone_el_hash_y_trae_roles_y_grupos(client, crear_usuario):
    crear_usuario()
    item = client.get(URL).json()["items"][0]
    assert "hashed_password" not in item
    assert {"roles", "groups", "totp_activo"} <= item.keys()


def test_el_listado_completo_sigue_igual(client, crear_usuario):
    """Grupos, Cajeros y el e2e piden `GET /users?per_page=500` y esperan `data`."""
    for i in range(3):
        crear_usuario(username=f"u{i}")
    r = client.get(BASE, params={"per_page": 500}).json()
    assert r["total"] == 3 and len(r["data"]) == 3 and r["per_page"] == 500


def test_search_no_choca_con_el_detalle_por_id(client, crear_usuario):
    u = crear_usuario()
    assert client.get(f"{BASE}/{u.id}").json()["username"] == u.username


# ── Orden ────────────────────────────────────────────────────────────


def test_ordena_por_nombre_por_defecto_y_usa_el_username_si_no_hay_nombre(client, crear_usuario):
    crear_usuario(username="zeta", full_name="Ana Zárate")
    crear_usuario(username="alfa", full_name="Carlos Alfa")
    crear_usuario(username="beto", full_name=None)
    assert _nombres(client.get(URL)) == ["zeta", "beto", "alfa"]


@pytest.mark.parametrize("sort,order,esperado", [
    ("username", "asc", ["alfa", "beto", "zeta"]),
    ("username", "desc", ["zeta", "beto", "alfa"]),
    ("email", "asc", ["beto", "zeta", "alfa"]),
    ("estado", "asc", ["beto", "zeta", "alfa"]),   # empate: por id de alta
])
def test_ordena_por_columna(client, crear_usuario, sort, order, esperado):
    crear_usuario(username="zeta", email="b@x.com")
    crear_usuario(username="alfa", email="c@x.com")
    crear_usuario(username="beto", email="a@x.com", is_active=False)
    assert _nombres(client.get(URL, params={"sort": sort, "order": order})) == esperado


# ── Filtros ──────────────────────────────────────────────────────────


def test_busca_por_usuario_email_o_nombre_sin_distinguir_mayusculas(client, crear_usuario):
    crear_usuario(username="mlopez", full_name="Maria Lopez", email="maria@capresca.gob.ar")
    crear_usuario(username="jperez", full_name="Juan Perez", email="jp@otro.com")
    crear_usuario(username="rgomez", full_name="Rita Gomez", email="rita@CAPRESCA.gob.ar")

    assert _nombres(client.get(URL, params={"q": "MLOP"})) == ["mlopez"]
    assert _nombres(client.get(URL, params={"q": "juan"})) == ["jperez"]
    assert _nombres(client.get(URL, params={"q": "capresca", "sort": "username"})) == ["mlopez", "rgomez"]
    assert len(_nombres(client.get(URL, params={"q": "   "}))) == 3


def test_la_busqueda_trata_comodines_como_texto(client, crear_usuario):
    crear_usuario(username="con_guion", email="a@x.com")
    crear_usuario(username="conxguion", email="b@x.com")
    crear_usuario(username="cien", full_name="100% real", email="c@x.com")
    assert _nombres(client.get(URL, params={"q": "con_"})) == ["con_guion"]
    assert _nombres(client.get(URL, params={"q": "%"})) == ["cien"]


def test_filtra_por_estado(client, crear_usuario):
    crear_usuario(username="activo")
    crear_usuario(username="baja", is_active=False)
    assert _nombres(client.get(URL, params={"estado": "activo"})) == ["activo"]
    assert _nombres(client.get(URL, params={"estado": "inactivo"})) == ["baja"]


def test_filtra_por_doble_factor(client, crear_usuario, db):
    con = crear_usuario(username="con2fa")
    crear_usuario(username="sin2fa")
    con.totp_activo = True
    db.commit()
    assert _nombres(client.get(URL, params={"mfa": "true"})) == ["con2fa"]
    assert _nombres(client.get(URL, params={"mfa": "false"})) == ["sin2fa"]


def test_filtra_por_rol_directo_o_heredado_de_un_grupo_activo(client, crear_usuario, crear_rol, grupo, db):
    rol = crear_rol(name="tesorero")
    otro = crear_rol(name="auditor")
    directo = crear_usuario(username="directo")
    heredado = crear_usuario(username="heredado")
    inactivo = crear_usuario(username="por_grupo_inactivo")
    crear_usuario(username="sin_rol")
    directo.roles = [rol]
    db.commit()
    grupo("Tesoreria", roles=[rol], users=[heredado])
    grupo("Viejo", roles=[rol], users=[inactivo], is_active=False)
    grupo("Auditoria", roles=[otro], users=[directo])

    r = client.get(URL, params={"role_id": rol.id, "sort": "username"})
    assert _nombres(r) == ["directo", "heredado"] and r.json()["total"] == 2


def test_filtra_por_grupo(client, crear_usuario, grupo):
    ana = crear_usuario(username="ana")
    crear_usuario(username="beto")
    g = grupo("Mesa", users=[ana])
    assert _nombres(client.get(URL, params={"group_id": g.id})) == ["ana"]


def test_combina_filtros_y_el_total_es_el_filtrado(client, crear_usuario):
    for i in range(30):
        crear_usuario(username=f"op{i:02d}", full_name=None, is_active=i % 2 == 0)
    crear_usuario(username="otro", full_name=None)
    r = client.get(URL, params={"q": "op", "estado": "activo", "page_size": 10, "page": 2}).json()
    assert r["total"] == 15 and r["pages"] == 2 and len(r["items"]) == 5
    assert all(u["is_active"] and u["username"].startswith("op") for u in r["items"])
