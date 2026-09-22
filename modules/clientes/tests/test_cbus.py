"""Tests de CBUs de clientes (alta, validación, cuenta de cobro y baja lógica)."""
import pytest
from sqlalchemy.exc import IntegrityError

CBU_A = "0720099620000001234501"
CBU_B = "0110012820000034567803"


def _alta_cbu(client, h, client_id, cbu=CBU_A, **extra):
    payload = {"cbu": cbu, "alias": "Cuenta principal", "bank_name": "BNA", "account_type": "CC"}
    payload.update(extra)
    return client.post(f"/api/clientes/{client_id}/cbus", json=payload, headers=h)


# ── Alta ────────────────────────────────────────────────────────
def test_alta_de_cbu(client, h, crear_pj):
    pj = crear_pj()
    r = _alta_cbu(client, h, pj["id"])
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["cbu"] == CBU_A
    assert data["client_id"] == pj["id"]
    assert data["created_by"] == 7
    assert data["is_active"] is True
    assert data["is_payment_account"] is False


def test_alta_de_cbu_recorta_espacios(client, h, crear_pj):
    pj = crear_pj()
    r = _alta_cbu(client, h, pj["id"], cbu=f"  {CBU_A}  ")
    assert r.status_code == 201
    assert r.json()["cbu"] == CBU_A


@pytest.mark.parametrize(
    "valor",
    ["123", "0720099620000001234501999", "07200996200000012345AB", ""],
)
def test_alta_de_cbu_invalido_es_422(client, h, crear_pj, valor):
    pj = crear_pj()
    r = _alta_cbu(client, h, pj["id"], cbu=valor)
    assert r.status_code == 422
    assert "22 dígitos" in r.text


def test_alta_de_cbu_sin_header_de_usuario_es_422(client, crear_pj):
    pj = crear_pj()
    r = client.post(f"/api/clientes/{pj['id']}/cbus", json={"cbu": CBU_A})
    assert r.status_code == 422


def test_cbu_duplicado_informa_la_razon_social_del_dueno(client, h, crear_pj):
    dueno = crear_pj(razon_social="Lotería El Dorado S.A.", cuit="30-1-1")
    otro = crear_pj(razon_social="Bingo Centro S.A.", cuit="30-2-2")
    assert _alta_cbu(client, h, dueno["id"]).status_code == 201

    r = _alta_cbu(client, h, otro["id"])
    assert r.status_code == 400
    assert "Lotería El Dorado S.A." in r.json()["detail"]


def test_cbu_duplicado_informa_el_nombre_de_la_persona_fisica(client, h, crear_ph):
    dueno = crear_ph(nombre="Juan", apellido="Pérez", documento="1")
    otro = crear_ph(nombre="Ana", apellido="Gómez", documento="2")
    assert _alta_cbu(client, h, dueno["id"]).status_code == 201

    r = _alta_cbu(client, h, otro["id"])
    assert r.status_code == 400
    assert "Juan Pérez" in r.json()["detail"]


def test_cbu_duplicado_de_un_cliente_sin_perfil_informa_el_id(client, h, db, crear_pj):
    """Si el dueño no tiene perfil cargado, el mensaje cae al id del cliente."""
    from app.models.client import Client, ClientType

    dueno = Client(client_type=ClientType.LEGAL, code="SIN-PERFIL", is_active=True)
    db.add(dueno)
    db.commit()
    otro = crear_pj()
    assert _alta_cbu(client, h, dueno.id).status_code == 201

    r = _alta_cbu(client, h, otro["id"])
    assert r.status_code == 400
    assert f"cliente {dueno.id}" in r.json()["detail"]


def test_recargar_un_cbu_dado_de_baja_rompe_por_unicidad(client, h, crear_pj):
    # TODO(bug): la baja es lógica (cbus.py:74) pero la columna `cbu` es UNIQUE sin
    # filtro: volver a cargar el mismo CBU pasa el chequeo de duplicados y explota
    # con IntegrityError (500) en vez de reactivar el registro.
    pj = crear_pj()
    creado = _alta_cbu(client, h, pj["id"]).json()
    assert client.delete(f"/api/clientes/{pj['id']}/cbus/{creado['id']}").status_code == 204

    with pytest.raises(IntegrityError):
        _alta_cbu(client, h, pj["id"])


# ── Listado ─────────────────────────────────────────────────────
def test_listado_de_cbus_solo_devuelve_activos(client, h, crear_pj):
    pj = crear_pj()
    uno = _alta_cbu(client, h, pj["id"], cbu=CBU_A).json()
    _alta_cbu(client, h, pj["id"], cbu=CBU_B)
    client.delete(f"/api/clientes/{pj['id']}/cbus/{uno['id']}")

    r = client.get(f"/api/clientes/{pj['id']}/cbus")
    assert r.status_code == 200
    assert [c["cbu"] for c in r.json()] == [CBU_B]


def test_listado_de_cbus_de_cliente_sin_cbus_es_vacio(client, crear_pj):
    pj = crear_pj()
    assert client.get(f"/api/clientes/{pj['id']}/cbus").json() == []


# ── Edición ─────────────────────────────────────────────────────
def test_editar_alias_y_banco_del_cbu(client, h, crear_pj):
    pj = crear_pj()
    creado = _alta_cbu(client, h, pj["id"]).json()
    r = client.put(
        f"/api/clientes/{pj['id']}/cbus/{creado['id']}",
        json={"alias": "Cuenta nueva", "bank_name": "Galicia", "description": "Cobros"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["alias"] == "Cuenta nueva"
    assert data["bank_name"] == "Galicia"
    assert data["description"] == "Cobros"
    # el CBU en sí no es editable por este endpoint
    assert data["cbu"] == CBU_A


def test_solo_un_cbu_por_cliente_puede_ser_cuenta_de_cobro(client, h, crear_pj):
    pj = crear_pj()
    uno = _alta_cbu(client, h, pj["id"], cbu=CBU_A, is_payment_account=True).json()
    dos = _alta_cbu(client, h, pj["id"], cbu=CBU_B).json()
    assert uno["is_payment_account"] is True

    r = client.put(f"/api/clientes/{pj['id']}/cbus/{dos['id']}", json={"is_payment_account": True})
    assert r.status_code == 200
    assert r.json()["is_payment_account"] is True

    cbus = {c["id"]: c for c in client.get(f"/api/clientes/{pj['id']}/cbus").json()}
    assert cbus[uno["id"]]["is_payment_account"] is False
    assert cbus[dos["id"]]["is_payment_account"] is True


def test_quitar_la_marca_de_cuenta_de_cobro(client, h, crear_pj):
    pj = crear_pj()
    creado = _alta_cbu(client, h, pj["id"], is_payment_account=True).json()
    r = client.put(f"/api/clientes/{pj['id']}/cbus/{creado['id']}", json={"is_payment_account": False})
    assert r.status_code == 200
    assert r.json()["is_payment_account"] is False


def test_editar_cbu_inexistente_es_404(client, crear_pj):
    pj = crear_pj()
    r = client.put(f"/api/clientes/{pj['id']}/cbus/9999", json={"alias": "x"})
    assert r.status_code == 404
    assert r.json()["detail"] == "CBU no encontrado"


def test_editar_cbu_de_otro_cliente_es_404(client, h, crear_pj):
    uno = crear_pj(razon_social="Uno", cuit="30-1-1")
    dos = crear_pj(razon_social="Dos", cuit="30-2-2")
    creado = _alta_cbu(client, h, uno["id"]).json()
    assert client.put(f"/api/clientes/{dos['id']}/cbus/{creado['id']}", json={"alias": "x"}).status_code == 404


# ── Baja ────────────────────────────────────────────────────────
def test_baja_logica_de_cbu(client, h, crear_pj, db):
    from app.models.client import ClientCbu

    pj = crear_pj()
    creado = _alta_cbu(client, h, pj["id"]).json()
    assert client.delete(f"/api/clientes/{pj['id']}/cbus/{creado['id']}").status_code == 204

    fila = db.query(ClientCbu).filter(ClientCbu.id == creado["id"]).first()
    assert fila is not None and fila.is_active is False


def test_baja_de_cbu_inexistente_es_404(client, crear_pj):
    pj = crear_pj()
    assert client.delete(f"/api/clientes/{pj['id']}/cbus/9999").status_code == 404
