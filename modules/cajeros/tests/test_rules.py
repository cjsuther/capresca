"""Reglas de autorización: alta, listado con filtros y baja lógica."""
from app.models.authorization_rule import AuthorizationRule

BASE = "/api/cajeros/rules"


def crear_regla(client, headers, **extra):
    payload = {"cajero_user_id": 7, "authorizer_user_id": 20, "currency": "ARS",
               "amount_limit": "1000.00"}
    payload.update(extra)
    return client.post(BASE, json=payload, headers=headers)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "cajeros"}


def test_alta_de_regla_guarda_el_creador_del_header(client, h, db):
    r = crear_regla(client, h, cajero_username="cajero7", authorizer_username="jefe20",
                    reference="CAJA-1")
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["created_by"] == 7  # lo inyecta el gateway en X-User-Id
    assert cuerpo["is_active"] is True
    assert cuerpo["amount_limit"] == "1000.00"
    assert db.query(AuthorizationRule).count() == 1


def test_alta_sin_identidad_o_con_identidad_invalida(client):
    assert crear_regla(client, {}).status_code == 422
    assert crear_regla(client, {"X-User-Id": "no-es-un-id"}).status_code == 401


def test_alta_valida_el_payload(client, h):
    assert client.post(BASE, json={"cajero_user_id": 7}, headers=h).status_code == 422
    assert crear_regla(client, h, amount_limit="mucho").status_code == 422


def test_listado_filtra_por_cajero_y_moneda_y_omite_inactivas(client, h, db):
    crear_regla(client, h, cajero_user_id=7, currency="ARS", amount_limit="100")
    crear_regla(client, h, cajero_user_id=7, currency="USD", amount_limit="200")
    crear_regla(client, h, cajero_user_id=9, currency="ARS", amount_limit="300")

    todas = client.get(BASE, headers=h).json()
    assert len(todas) == 3

    assert len(client.get(f"{BASE}?cajero=7", headers=h).json()) == 2
    assert len(client.get(f"{BASE}?currency=USD", headers=h).json()) == 1
    assert len(client.get(f"{BASE}?cajero=7&currency=USD", headers=h).json()) == 1

    regla = db.query(AuthorizationRule).filter_by(cajero_user_id=9).one()
    assert client.delete(f"{BASE}/{regla.id}", headers=h).status_code == 204
    assert len(client.get(BASE, headers=h).json()) == 2


def test_baja_es_logica_y_no_borra_la_fila(client, h, db):
    regla_id = crear_regla(client, h).json()["id"]
    assert client.delete(f"{BASE}/{regla_id}", headers=h).status_code == 204
    fila = db.query(AuthorizationRule).filter_by(id=regla_id).one()
    assert fila.is_active is False


def test_baja_de_regla_inexistente_da_404(client, h):
    assert client.delete(f"{BASE}/999", headers=h).status_code == 404


def test_cualquier_usuario_puede_dar_de_baja_una_regla_ajena(client, h, db):
    # TODO(bug): rule_service.delete_rule recibe user_id pero nunca lo valida
    # (app/services/rule_service.py:24-29): cualquier identidad borra cualquier regla.
    regla_id = crear_regla(client, h).json()["id"]
    assert client.delete(f"{BASE}/{regla_id}", headers={"X-User-Id": "999"}).status_code == 204
    assert db.query(AuthorizationRule).filter_by(id=regla_id).one().is_active is False
