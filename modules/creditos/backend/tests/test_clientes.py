"""
Clientes en Créditos = ESPEJO del padrón de Portezuelo (módulo Clientes).

El alta/edición/baja de la persona se hacen en el módulo Clientes; acá sólo se lee el espejo, se lo
sincroniza contra el padrón y se editan los datos crediticios (sueldo, organismo, débito automático).
"""
import pytest
from fastapi.testclient import TestClient

from app.core import clientes_padron


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


FICHA = {
    "client_id": 77, "codigo": "PH-0077", "tipo": "HUMAN", "nombre": "LOPEZ, MARIA",
    "apellido": "LOPEZ", "nombres": "MARIA", "razon_social": None,
    "tipo_documento": "CUIL", "documento": "20999999994", "fecha_nacimiento": None, "sexo": "F",
    "email": "maria@ejemplo.com", "telefono": "3834-111111", "domicilio": "SAN MARTIN 100",
    "localidad": "SFV CATAMARCA", "cbu": "0110466420046600520531", "activo": True,
}


def test_el_maestro_de_clientes_ya_no_se_administra_aca(client):
    """El padrón es del módulo Clientes: Créditos no expone alta, edición ni baja de personas."""
    h = _auth(client)
    body = {"id_cliente": "T001", "cuil": "20111111112", "apellido_nombre": "TEST UNO"}
    assert client.post("/api/creditos/clientes", headers=h, json=body).status_code == 405
    assert client.put("/api/creditos/clientes/1", headers=h, json={"apellido_nombre": "OTRO"}).status_code == 405
    assert client.post("/api/creditos/clientes/1/baja", headers=h, json={"motivo": "x"}).status_code == 404


def test_lista_y_detalle_leen_el_espejo(client):
    h = _auth(client)
    items = client.get("/api/creditos/clientes", headers=h).json()["items"]
    assert items and all("apellido_nombre" in c for c in items)
    uno = client.get(f"/api/creditos/clientes/{items[0]['id']}", headers=h)
    assert uno.status_code == 200 and uno.json()["id"] == items[0]["id"]


def test_sincronizar_trae_la_identidad_del_padron(client, monkeypatch):
    """La identidad viene del padrón; el espejo se crea con el MISMO id que allá."""
    h = _auth(client)
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: dict(FICHA, client_id=cid))

    r = client.post("/api/creditos/clientes/77/sincronizar", headers=h)
    assert r.status_code == 200
    c = r.json()
    assert c["id"] == 77                                  # el id es el del padrón, no una secuencia local
    assert c["apellido_nombre"] == "LOPEZ, MARIA"
    assert c["cuil"] == "20999999994"
    assert c["cbu"] == "0110466420046600520531"

    # Y queda espejado: el GET ya no necesita ir al padrón.
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: (_ for _ in ()).throw(AssertionError("no debía consultar")))
    assert client.get("/api/creditos/clientes/77", headers=h).json()["apellido_nombre"] == "LOPEZ, MARIA"


def test_consultar_un_cliente_nuevo_lo_espeja_al_vuelo(client, monkeypatch):
    h = _auth(client)
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: dict(FICHA, client_id=cid, nombre="NUEVA, PERSONA"))
    r = client.get("/api/creditos/clientes/1234", headers=h)
    assert r.status_code == 200 and r.json()["apellido_nombre"] == "NUEVA, PERSONA"


def test_cliente_inexistente_en_el_padron_es_404(client, monkeypatch):
    h = _auth(client)
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: None)
    assert client.get("/api/creditos/clientes/999999", headers=h).status_code == 404
    assert client.post("/api/creditos/clientes/999999/sincronizar", headers=h).status_code == 404


def test_si_el_padron_no_responde_se_sigue_con_el_espejo(client, monkeypatch):
    """Degradación elegante: una caída del módulo Clientes no puede voltear las pantallas de Créditos."""
    h = _auth(client)

    def _cae(_cid):
        raise clientes_padron.PadronNoDisponible("connection refused")

    monkeypatch.setattr(clientes_padron, "ficha", _cae)
    r = client.get("/api/creditos/clientes/1", headers=h)    # ya espejado por el seed
    assert r.status_code == 200 and r.json()["id"] == 1


def test_perfil_crediticio_edita_lo_de_creditos_y_no_la_identidad(client):
    h = _auth(client)
    antes = client.get("/api/creditos/clientes/1", headers=h).json()
    r = client.put("/api/creditos/clientes/1/perfil-crediticio", headers=h,
                   json={"sueldo": "999000", "debito_automatico": True, "apellido_nombre": "HACKEADO"})
    assert r.status_code == 200
    c = r.json()
    assert float(c["sueldo"]) == 999000 and c["debito_automatico"] is True
    assert c["apellido_nombre"] == antes["apellido_nombre"]   # la identidad sólo la cambia el padrón


def test_escritura_exige_permiso_backend(client):
    """H-156/H-205: el nivel se enforca también en el BACKEND, detrás del gateway."""
    gw = lambda *perms: {"X-User-Id": "901", "X-Username": "pz.creditos", "X-User-Permissions": ",".join(perms)}
    solo_lectura = gw("creditos:creditos:read")
    con_escritura = gw("creditos:creditos:read", "creditos:creditos:write")
    assert client.put("/api/creditos/clientes/1/perfil-crediticio", headers=solo_lectura,
                      json={"sueldo": "1"}).status_code == 403
    assert client.put("/api/creditos/clientes/1/perfil-crediticio", headers=con_escritura,
                      json={"sueldo": "1"}).status_code == 200
