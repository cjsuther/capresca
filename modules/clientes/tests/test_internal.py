"""Tests de los endpoints internos que consumen otros módulos del sistema."""

CBU_A = "0720099620000001234501"
CBU_B = "0110012820000034567803"


def _alta_cbu(client, h, client_id, cbu=CBU_A, **extra):
    payload = {"cbu": cbu, "alias": "Principal", "bank_name": "BNA", "account_type": "CC"}
    payload.update(extra)
    r = client.post(f"/api/clientes/{client_id}/cbus", json=payload, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


# ── Agencias ────────────────────────────────────────────────────
def test_agencias_devuelve_solo_juridicas_con_numero_de_agencia(client, h, crear_pj, crear_ph):
    con_agencia = crear_pj(razon_social="Lotería El Dorado S.A.", cuit="30-1-1", agencia="A001")
    crear_pj(razon_social="Sin Agencia S.A.", cuit="30-2-2")
    crear_ph()
    _alta_cbu(client, h, con_agencia["id"], cbu=CBU_A, is_payment_account=True)
    _alta_cbu(client, h, con_agencia["id"], cbu=CBU_B)

    r = client.get("/internal/clientes/agencies")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    agencia = data[0]
    assert agencia["agency_number"] == "A001"
    assert agencia["legal_name"] == "Lotería El Dorado S.A."
    assert agencia["tax_id"] == "30-1-1"
    assert len(agencia["cbus"]) == 2
    assert [c["is_payment_account"] for c in agencia["cbus"]] == [True, False]


def test_agencias_excluye_las_dadas_de_baja(client, crear_pj):
    pj = crear_pj(agencia="A009")
    client.delete(f"/api/clientes/{pj['id']}")
    assert client.get("/internal/clientes/agencies").json() == []


def test_agencias_sin_datos_devuelve_lista_vacia(client):
    assert client.get("/internal/clientes/agencies").json() == []


# ── Búsqueda por CBU ────────────────────────────────────────────
def test_buscar_por_cbu_devuelve_la_agencia(client, h, crear_pj):
    pj = crear_pj(razon_social="Bingo Centro S.A.", agencia="A003")
    _alta_cbu(client, h, pj["id"])

    r = client.get(f"/internal/clientes/cbu/{CBU_A}")
    assert r.status_code == 200
    assert r.json() == {
        "client_id": pj["id"],
        "agency_number": "A003",
        "legal_name": "Bingo Centro S.A.",
    }


def test_buscar_por_cbu_de_persona_fisica_no_trae_datos_de_agencia(client, h, crear_ph):
    ph = crear_ph()
    _alta_cbu(client, h, ph["id"])

    r = client.get(f"/internal/clientes/cbu/{CBU_A}")
    assert r.status_code == 200
    assert r.json() == {"client_id": ph["id"], "agency_number": None, "legal_name": None}


def test_buscar_por_cbu_inexistente_es_404(client):
    r = client.get(f"/internal/clientes/cbu/{CBU_A}")
    assert r.status_code == 404
    assert r.json()["detail"] == "CBU no registrado"


def test_buscar_por_cbu_dado_de_baja_es_404(client, h, crear_pj):
    pj = crear_pj()
    creado = _alta_cbu(client, h, pj["id"])
    client.delete(f"/api/clientes/{pj['id']}/cbus/{creado['id']}")
    assert client.get(f"/internal/clientes/cbu/{CBU_A}").status_code == 404


# ── Búsqueda por teléfono ───────────────────────────────────────
def test_buscar_por_telefono_principal(client, crear_ph):
    ph = crear_ph(phone="2604111222")
    r = client.get("/internal/clientes/by-phone/2604111222")
    assert r.status_code == 200
    assert r.json() == {
        "client_id": ph["id"],
        "client_name": "Juan Pérez",
        "client_type": "HUMAN",
        "phone": "2604111222",
    }


def test_buscar_por_telefono_en_contactos(client, crear_pj):
    pj = crear_pj(razon_social="Agencia Sur S.A.")
    client.post(
        f"/api/clientes/{pj['id']}/contacts",
        json={"contact_type": "whatsapp", "value": "2604999888", "label": "Ventas"},
    )
    r = client.get("/internal/clientes/by-phone/2604999888")
    assert r.status_code == 200
    assert r.json()["client_id"] == pj["id"]
    assert r.json()["client_name"] == "Agencia Sur S.A."
    assert r.json()["client_type"] == "LEGAL"


def test_buscar_por_telefono_ignora_contactos_que_no_son_telefonicos(client, crear_ph):
    ph = crear_ph()
    client.post(
        f"/api/clientes/{ph['id']}/contacts",
        json={"contact_type": "email", "value": "2604999888"},
    )
    r = client.get("/internal/clientes/by-phone/2604999888")
    assert r.status_code == 200
    assert r.json() is None


def test_buscar_por_telefono_inexistente_devuelve_null(client):
    r = client.get("/internal/clientes/by-phone/0000000")
    assert r.status_code == 200
    assert r.json() is None


def test_buscar_por_telefono_de_cliente_dado_de_baja_devuelve_null(client, crear_ph):
    ph = crear_ph(phone="2604111222")
    client.delete(f"/api/clientes/{ph['id']}")
    assert client.get("/internal/clientes/by-phone/2604111222").json() is None


def test_nombre_de_cliente_sin_perfil_cae_al_codigo(client, db):
    from app.models.client import Client, ClientType

    cli = Client(client_type=ClientType.HUMAN, code="PH-SINPERFIL", phone="2604000111", is_active=True)
    db.add(cli)
    db.commit()

    r = client.get("/internal/clientes/by-phone/2604000111")
    assert r.json()["client_name"] == "PH-SINPERFIL"


# ── Datos básicos por id ────────────────────────────────────────
def test_datos_internos_de_un_cliente(client, crear_pj):
    pj = crear_pj(razon_social="Agencia Sur S.A.", phone="2604555444")
    r = client.get(f"/internal/clientes/{pj['id']}")
    assert r.status_code == 200
    data = r.json()
    assert data["client_name"] == "Agencia Sur S.A."
    assert data["client_type"] == "LEGAL"
    assert data["email"] == "contacto@agenciasur.com"


def test_datos_internos_de_cliente_inexistente_devuelve_null(client):
    r = client.get("/internal/clientes/9999")
    assert r.status_code == 200
    assert r.json() is None


def test_datos_internos_de_cliente_dado_de_baja_devuelve_null(client, crear_ph):
    ph = crear_ph()
    client.delete(f"/api/clientes/{ph['id']}")
    assert client.get(f"/internal/clientes/{ph['id']}").json() is None


# ── Teléfonos de un cliente ─────────────────────────────────────
def test_telefonos_de_un_cliente_incluyen_principal_y_contactos(client, crear_ph):
    ph = crear_ph(phone="2604111222")
    client.post(
        f"/api/clientes/{ph['id']}/contacts",
        json={"contact_type": "whatsapp", "value": "2604999888", "label": "Personal"},
    )
    client.post(
        f"/api/clientes/{ph['id']}/contacts",
        json={"contact_type": "celular", "value": "2604777666"},
    )
    client.post(
        f"/api/clientes/{ph['id']}/contacts",
        json={"contact_type": "email", "value": "otro@example.com"},
    )

    r = client.get(f"/internal/clientes/{ph['id']}/phones")
    assert r.status_code == 200
    telefonos = r.json()
    assert [t["phone"] for t in telefonos] == ["2604111222", "2604999888", "2604777666"]
    assert telefonos[0]["type"] == "principal"
    assert telefonos[1]["label"] == "Personal"
    # sin label, se usa el tipo de contacto
    assert telefonos[2]["label"] == "celular"


def test_telefonos_de_cliente_sin_telefono_es_lista_vacia(client, crear_ph):
    ph = crear_ph()
    assert client.get(f"/internal/clientes/{ph['id']}/phones").json() == []


def test_telefonos_de_cliente_inexistente_es_lista_vacia(client):
    r = client.get("/internal/clientes/9999/phones")
    assert r.status_code == 200
    assert r.json() == []
