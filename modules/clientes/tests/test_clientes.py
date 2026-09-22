"""Tests de alta, edición, búsqueda, contactos, notas y miembros de clientes."""
import pytest
from sqlalchemy.exc import IntegrityError


# ── Salud ───────────────────────────────────────────────────────
def test_health_responde_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "clientes"}


# ── Alta de personas físicas ────────────────────────────────────
def test_alta_persona_fisica_genera_codigo_y_perfil(client, h):
    r = client.post(
        "/api/clientes/human",
        json={
            "email": "juan@example.com",
            "phone": "2604111222",
            "address": "San Martín 100",
            "city": "Mendoza",
            "country": "AR",
            "profile": {
                "first_name": "Juan",
                "last_name": "Pérez",
                "document_type": "DNI",
                "document_number": "20304050",
                "birth_date": "1985-04-12",
                "gender": "M",
                "nationality": "Argentina",
            },
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["client_type"] == "HUMAN"
    assert data["code"].startswith("PH-")
    assert data["is_active"] is True
    assert data["human_profile"]["first_name"] == "Juan"
    assert data["human_profile"]["document_number"] == "20304050"
    assert data["legal_profile"] is None
    assert data["contacts"] == []


def test_alta_persona_fisica_usa_country_por_defecto(client, h):
    r = client.post(
        "/api/clientes/human",
        json={"profile": {"first_name": "Ana", "last_name": "Gómez"}},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["country"] == "AR"


def test_alta_guarda_el_usuario_que_la_creo(client, db):
    from app.models.client import Client

    client.post(
        "/api/clientes/human",
        json={"profile": {"first_name": "Ana", "last_name": "Gómez"}},
        headers={"X-User-Id": "42"},
    )
    creado = db.query(Client).first()
    assert creado.created_by_user_id == 42


def test_alta_sin_header_de_usuario_es_422(client):
    r = client.post(
        "/api/clientes/human",
        json={"profile": {"first_name": "Ana", "last_name": "Gómez"}},
    )
    assert r.status_code == 422


def test_alta_con_header_de_usuario_invalido_es_401(client):
    r = client.post(
        "/api/clientes/human",
        json={"profile": {"first_name": "Ana", "last_name": "Gómez"}},
        headers={"X-User-Id": "no-soy-un-id"},
    )
    assert r.status_code == 401
    assert "X-User-Id" in r.json()["detail"]


def test_alta_persona_fisica_sin_perfil_es_422(client, h):
    r = client.post("/api/clientes/human", json={"email": "x@y.com"}, headers=h)
    assert r.status_code == 422


def test_alta_persona_fisica_sin_apellido_es_422(client, h):
    r = client.post(
        "/api/clientes/human",
        json={"profile": {"first_name": "Ana"}},
        headers=h,
    )
    assert r.status_code == 422


def test_dos_personas_fisicas_con_el_mismo_documento_se_permiten(client, crear_ph, db):
    # TODO(bug): no hay validación de duplicados por DNI/CUIL (client_service.py:68);
    # el módulo acepta dos personas físicas con el mismo document_number.
    crear_ph(nombre="Juan", documento="20304050")
    crear_ph(nombre="Juan Carlos", documento="20304050")
    r = client.get("/api/clientes", params={"search": "20304050"})
    assert r.json()["total"] == 2


# ── Alta de personas jurídicas ──────────────────────────────────
def test_alta_persona_juridica_genera_codigo_pj(client, h):
    r = client.post(
        "/api/clientes/legal",
        json={
            "email": "contacto@eldorado.com",
            "city": "San Rafael",
            "profile": {
                "legal_name": "Lotería El Dorado S.A.",
                "trade_name": "El Dorado",
                "tax_id": "30-71234567-8",
                "tax_id_type": "CUIT",
                "incorporation_date": "2001-09-01",
                "legal_representative": "María López",
                "industry_sector": "Juegos de azar",
                "agency_number": "A001",
            },
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["client_type"] == "LEGAL"
    assert data["code"].startswith("PJ-")
    assert data["legal_profile"]["agency_number"] == "A001"
    assert data["human_profile"] is None


def test_alta_persona_juridica_sin_razon_social_es_422(client, h):
    r = client.post("/api/clientes/legal", json={"profile": {"tax_id": "30-1-1"}}, headers=h)
    assert r.status_code == 422


def test_dos_personas_juridicas_con_el_mismo_cuit_se_permiten(client, crear_pj):
    # TODO(bug): tax_id no es único ni se valida (client_service.py:89); el CUIT
    # repetido entra sin error mientras agency_number sea distinto.
    crear_pj(razon_social="Agencia Uno", cuit="30-71234567-8")
    crear_pj(razon_social="Agencia Dos", cuit="30-71234567-8")
    r = client.get("/api/clientes", params={"search": "30-71234567-8"})
    assert r.json()["total"] == 2


def test_numero_de_agencia_duplicado_rompe_con_error_de_integridad(crear_pj):
    # TODO(bug): agency_number es UNIQUE en la tabla pero el servicio no lo valida
    # (client_service.py:89-107): el duplicado escapa como IntegrityError -> 500.
    crear_pj(razon_social="Agencia Uno", agencia="A001")
    with pytest.raises(IntegrityError):
        crear_pj(razon_social="Agencia Dos", agencia="A001")


# ── Detalle ─────────────────────────────────────────────────────
def test_detalle_devuelve_el_cliente(client, crear_ph):
    cli = crear_ph()
    r = client.get(f"/api/clientes/{cli['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == cli["id"]


def test_detalle_de_cliente_inexistente_es_404(client):
    r = client.get("/api/clientes/9999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Cliente no encontrado"


def test_detalle_con_id_no_numerico_es_422(client):
    r = client.get("/api/clientes/abc")
    assert r.status_code == 422


# ── Edición ─────────────────────────────────────────────────────
def test_editar_datos_base(client, crear_ph):
    cli = crear_ph()
    r = client.put(
        f"/api/clientes/{cli['id']}",
        json={"email": "nuevo@example.com", "city": "Malargüe", "phone": "2604999888"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "nuevo@example.com"
    assert data["city"] == "Malargüe"
    assert data["phone"] == "2604999888"


def test_editar_datos_base_con_null_no_borra_el_valor(client, crear_ph):
    # TODO(bug): update_client_base usa exclude_none (client_service.py:112), así que
    # no hay forma de vaciar un campo opcional desde la API.
    cli = crear_ph(email="original@example.com")
    r = client.put(f"/api/clientes/{cli['id']}", json={"email": None})
    assert r.status_code == 200
    assert r.json()["email"] == "original@example.com"


def test_editar_datos_base_de_inexistente_es_404(client):
    r = client.put("/api/clientes/9999", json={"city": "Mendoza"})
    assert r.status_code == 404


def test_editar_perfil_de_persona_fisica(client, crear_ph):
    cli = crear_ph()
    r = client.put(
        f"/api/clientes/{cli['id']}/human",
        json={"first_name": "Juan Manuel", "last_name": "Pérez", "nationality": "Argentina"},
    )
    assert r.status_code == 200
    perfil = r.json()["human_profile"]
    assert perfil["first_name"] == "Juan Manuel"
    assert perfil["nationality"] == "Argentina"
    # el documento original se conserva
    assert perfil["document_number"] == "20304050"


def test_editar_perfil_humano_sobre_persona_juridica_es_400(client, crear_pj):
    cli = crear_pj()
    r = client.put(
        f"/api/clientes/{cli['id']}/human",
        json={"first_name": "Juan", "last_name": "Pérez"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "El cliente no es persona humana"


def test_editar_perfil_de_persona_juridica(client, crear_pj):
    cli = crear_pj()
    r = client.put(
        f"/api/clientes/{cli['id']}/legal",
        json={"legal_name": "Agencia Sur S.R.L.", "industry_sector": "Quiniela"},
    )
    assert r.status_code == 200
    perfil = r.json()["legal_profile"]
    assert perfil["legal_name"] == "Agencia Sur S.R.L."
    assert perfil["industry_sector"] == "Quiniela"


def test_editar_perfil_juridico_sobre_persona_fisica_es_400(client, crear_ph):
    cli = crear_ph()
    r = client.put(f"/api/clientes/{cli['id']}/legal", json={"legal_name": "X S.A."})
    assert r.status_code == 400
    assert r.json()["detail"] == "El cliente no es persona jurídica"


def test_editar_perfil_de_cliente_inexistente_es_404(client):
    r = client.put("/api/clientes/9999/human", json={"first_name": "A", "last_name": "B"})
    assert r.status_code == 404


# ── Baja lógica ─────────────────────────────────────────────────
def test_baja_logica_desactiva_y_lo_saca_del_listado(client, crear_ph):
    cli = crear_ph()
    r = client.delete(f"/api/clientes/{cli['id']}")
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    # sigue accesible por detalle pero no aparece en el listado
    assert client.get(f"/api/clientes/{cli['id']}").status_code == 200
    assert client.get("/api/clientes").json()["total"] == 0


def test_baja_logica_de_inexistente_es_404(client):
    assert client.delete("/api/clientes/9999").status_code == 404


# ── Listado, filtros y paginación ───────────────────────────────
def test_listado_vacio(client):
    r = client.get("/api/clientes")
    assert r.status_code == 200
    assert r.json() == {"data": [], "total": 0, "page": 1, "per_page": 20}


def test_listado_pagina_los_resultados(client, crear_ph):
    for i in range(5):
        crear_ph(nombre=f"Cliente{i}", documento=f"3000000{i}")

    pag1 = client.get("/api/clientes", params={"page": 1, "per_page": 2}).json()
    assert pag1["total"] == 5
    assert len(pag1["data"]) == 2
    assert pag1["per_page"] == 2

    pag3 = client.get("/api/clientes", params={"page": 3, "per_page": 2}).json()
    assert len(pag3["data"]) == 1
    assert pag3["page"] == 3

    vacia = client.get("/api/clientes", params={"page": 9, "per_page": 2}).json()
    assert vacia["data"] == []
    assert vacia["total"] == 5


@pytest.mark.parametrize("params", [{"page": 0}, {"per_page": 0}, {"per_page": 101}])
def test_listado_rechaza_paginacion_invalida(client, params):
    assert client.get("/api/clientes", params=params).status_code == 422


def test_listado_filtra_por_tipo_sin_importar_mayusculas(client, crear_ph, crear_pj):
    crear_ph()
    crear_pj()

    humanos = client.get("/api/clientes", params={"client_type": "human"}).json()
    assert humanos["total"] == 1
    assert humanos["data"][0]["client_type"] == "HUMAN"

    juridicos = client.get("/api/clientes", params={"client_type": "LEGAL"}).json()
    assert juridicos["total"] == 1
    assert juridicos["data"][0]["client_type"] == "LEGAL"


def test_listado_filtra_por_ciudad_parcial(client, crear_ph):
    crear_ph(nombre="Uno", documento="1", city="San Rafael")
    crear_ph(nombre="Dos", documento="2", city="Mendoza")
    r = client.get("/api/clientes", params={"city": "rafa"})
    assert r.json()["total"] == 1


@pytest.mark.parametrize(
    "termino",
    ["Juan", "Pérez", "20304050", "juan@example.com"],
)
def test_busqueda_de_persona_fisica_por_varios_campos(client, crear_ph, termino):
    crear_ph(nombre="Juan", apellido="Pérez", documento="20304050")
    crear_ph(nombre="Carlos", apellido="Díaz", documento="99999999")
    r = client.get("/api/clientes", params={"search": termino})
    assert r.json()["total"] == 1


@pytest.mark.parametrize("termino", ["Dorado", "El Dora", "30-71234567-8"])
def test_busqueda_de_persona_juridica_por_varios_campos(client, crear_pj, termino):
    crear_pj(razon_social="Lotería El Dorado S.A.", cuit="30-71234567-8", trade_name="El Dora SRL")
    crear_pj(razon_social="Bingo Centro", cuit="30-11111111-1", trade_name="Bingo")
    r = client.get("/api/clientes", params={"search": termino})
    assert r.json()["total"] == 1


def test_busqueda_sin_resultados(client, crear_ph):
    crear_ph()
    assert client.get("/api/clientes", params={"search": "inexistente"}).json()["total"] == 0


def test_busqueda_no_devuelve_clientes_dados_de_baja(client, crear_ph):
    cli = crear_ph()
    client.delete(f"/api/clientes/{cli['id']}")
    assert client.get("/api/clientes", params={"search": "Juan"}).json()["total"] == 0


def test_endpoint_search_dedicado(client, crear_ph):
    crear_ph(nombre="Juan", documento="1")
    crear_ph(nombre="Carlos", documento="2")
    r = client.get("/api/clientes/search", params={"q": "Juan"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["data"][0]["human_profile"]["first_name"] == "Juan"


def test_endpoint_search_sin_q_es_422(client):
    assert client.get("/api/clientes/search").status_code == 422


def test_endpoint_search_no_limita_el_per_page(client, crear_ph):
    # TODO(bug): /search declara per_page sin ge/le (clients.py:45), a diferencia del
    # listado que lo acota a 100. Permite pedir páginas arbitrariamente grandes.
    crear_ph()
    r = client.get("/api/clientes/search", params={"q": "Juan", "per_page": 5000})
    assert r.status_code == 200
    assert r.json()["per_page"] == 5000


# ── Contactos ───────────────────────────────────────────────────
def test_alta_y_listado_de_contactos(client, crear_ph):
    cli = crear_ph()
    r = client.post(
        f"/api/clientes/{cli['id']}/contacts",
        json={"contact_type": "whatsapp", "value": "2604111222", "label": "Personal", "is_primary": True},
    )
    assert r.status_code == 201, r.text
    creado = r.json()
    assert creado["contact_type"] == "whatsapp"
    assert creado["is_primary"] is True

    listado = client.get(f"/api/clientes/{cli['id']}/contacts")
    assert listado.status_code == 200
    assert len(listado.json()) == 1


def test_alta_de_contacto_sobre_cliente_inexistente_es_404(client):
    r = client.post("/api/clientes/9999/contacts", json={"contact_type": "email", "value": "a@b.com"})
    assert r.status_code == 404


def test_alta_de_contacto_sin_valor_es_422(client, crear_ph):
    cli = crear_ph()
    r = client.post(f"/api/clientes/{cli['id']}/contacts", json={"contact_type": "email"})
    assert r.status_code == 422


def test_listado_de_contactos_de_cliente_inexistente_es_404(client):
    assert client.get("/api/clientes/9999/contacts").status_code == 404


def test_baja_de_contacto(client, crear_ph):
    cli = crear_ph()
    contacto = client.post(
        f"/api/clientes/{cli['id']}/contacts",
        json={"contact_type": "email", "value": "otro@example.com"},
    ).json()

    r = client.delete(f"/api/clientes/{cli['id']}/contacts/{contacto['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/clientes/{cli['id']}/contacts").json() == []


def test_baja_de_contacto_inexistente_es_404(client, crear_ph):
    cli = crear_ph()
    r = client.delete(f"/api/clientes/{cli['id']}/contacts/9999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Contacto no encontrado"


def test_baja_de_contacto_de_otro_cliente_es_404(client, crear_ph):
    uno = crear_ph(nombre="Uno", documento="1")
    dos = crear_ph(nombre="Dos", documento="2")
    contacto = client.post(
        f"/api/clientes/{uno['id']}/contacts",
        json={"contact_type": "email", "value": "a@b.com"},
    ).json()
    assert client.delete(f"/api/clientes/{dos['id']}/contacts/{contacto['id']}").status_code == 404


# ── Notas ───────────────────────────────────────────────────────
def test_alta_de_nota_guarda_el_autor(client, crear_ph):
    cli = crear_ph()
    r = client.post(
        f"/api/clientes/{cli['id']}/notes",
        json={"content": "Llamar el lunes"},
        headers={"X-User-Id": "13"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["user_id"] == 13
    assert r.json()["content"] == "Llamar el lunes"


def test_listado_de_notas(client, crear_ph, h):
    cli = crear_ph()
    for texto in ("primera", "segunda"):
        client.post(f"/api/clientes/{cli['id']}/notes", json={"content": texto}, headers=h)

    r = client.get(f"/api/clientes/{cli['id']}/notes")
    assert r.status_code == 200
    assert {n["content"] for n in r.json()} == {"primera", "segunda"}


def test_alta_de_nota_sobre_cliente_inexistente_es_404(client, h):
    r = client.post("/api/clientes/9999/notes", json={"content": "hola"}, headers=h)
    assert r.status_code == 404


def test_listado_de_notas_de_cliente_inexistente_devuelve_vacio(client):
    # get_notes no valida el cliente (client_service.py:182): lista vacía en vez de 404.
    r = client.get("/api/clientes/9999/notes")
    assert r.status_code == 200
    assert r.json() == []


def test_alta_de_nota_sin_contenido_es_422(client, crear_ph, h):
    cli = crear_ph()
    assert client.post(f"/api/clientes/{cli['id']}/notes", json={}, headers=h).status_code == 422


# ── Miembros de personas jurídicas ──────────────────────────────
def test_alta_y_listado_de_miembros(client, crear_ph, crear_pj):
    pj = crear_pj()
    ph = crear_ph()

    r = client.post(
        f"/api/clientes/{pj['id']}/members",
        json={"human_client_id": ph["id"], "role": "Socio"},
    )
    assert r.status_code == 201, r.text
    miembro = r.json()
    assert miembro["role"] == "Socio"
    assert miembro["human_client"]["id"] == ph["id"]

    listado = client.get(f"/api/clientes/{pj['id']}/members")
    assert listado.status_code == 200
    assert len(listado.json()) == 1
    assert listado.json()[0]["human_client"]["human_profile"]["last_name"] == "Pérez"


def test_alta_de_miembro_duplicado_es_409(client, crear_ph, crear_pj):
    pj = crear_pj()
    ph = crear_ph()
    body = {"human_client_id": ph["id"], "role": "Socio"}
    assert client.post(f"/api/clientes/{pj['id']}/members", json=body).status_code == 201

    r = client.post(f"/api/clientes/{pj['id']}/members", json=body)
    assert r.status_code == 409
    assert r.json()["detail"] == "El miembro ya pertenece a esta persona jurídica"


def test_no_se_pueden_agregar_miembros_a_una_persona_fisica(client, crear_ph):
    titular = crear_ph(nombre="Titular", documento="1")
    otro = crear_ph(nombre="Otro", documento="2")
    r = client.post(f"/api/clientes/{titular['id']}/members", json={"human_client_id": otro["id"]})
    assert r.status_code == 400
    assert r.json()["detail"] == "El cliente no es persona jurídica"


def test_un_miembro_no_puede_ser_persona_juridica(client, crear_pj):
    pj = crear_pj(razon_social="Madre S.A.", cuit="30-1-1")
    otra = crear_pj(razon_social="Hija S.A.", cuit="30-2-2")
    r = client.post(f"/api/clientes/{pj['id']}/members", json={"human_client_id": otra["id"]})
    assert r.status_code == 400
    assert r.json()["detail"] == "El miembro debe ser persona física"


def test_alta_de_miembro_inexistente_es_404(client, crear_pj):
    pj = crear_pj()
    r = client.post(f"/api/clientes/{pj['id']}/members", json={"human_client_id": 9999})
    assert r.status_code == 404


def test_listado_de_miembros_sobre_persona_fisica_es_400(client, crear_ph):
    cli = crear_ph()
    r = client.get(f"/api/clientes/{cli['id']}/members")
    assert r.status_code == 400


def test_listado_de_miembros_de_cliente_inexistente_es_404(client):
    assert client.get("/api/clientes/9999/members").status_code == 404


def test_baja_de_miembro(client, crear_ph, crear_pj):
    pj = crear_pj()
    ph = crear_ph()
    miembro = client.post(
        f"/api/clientes/{pj['id']}/members", json={"human_client_id": ph["id"]}
    ).json()

    r = client.delete(f"/api/clientes/{pj['id']}/members/{miembro['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/clientes/{pj['id']}/members").json() == []


def test_baja_de_miembro_inexistente_es_404(client, crear_pj):
    pj = crear_pj()
    r = client.delete(f"/api/clientes/{pj['id']}/members/9999")
    assert r.status_code == 404
    assert r.json()["detail"] == "Miembro no encontrado"
