"""ABM de impuestos e índices de referencia."""
import pytest

IVA = {"codigo": " iva21 ", "nombre": "IVA 21%", "tipo": "IVA", "alicuota": 21, "base": "INTERES",
       "cuenta_contable": "2.1.07.01"}


def test_sin_identidad_del_gateway_es_401(client):
    assert client.get("/api/configuraciones/impuestos").status_code == 401


def test_alta_normaliza_el_codigo_y_lista(client, admin):
    r = client.post("/api/configuraciones/impuestos", json=IVA, headers=admin)
    assert r.status_code == 201, r.text
    assert r.json()["codigo"] == "IVA21" and r.json()["alicuota"] == 21.0
    d = client.get("/api/configuraciones/impuestos", headers=admin).json()
    assert d["total"] == 1 and d["items"][0]["nombre"] == "IVA 21%"


def test_codigo_repetido_es_409(client, admin):
    client.post("/api/configuraciones/impuestos", json=IVA, headers=admin)
    r = client.post("/api/configuraciones/impuestos", json={**IVA, "codigo": "IVA21"}, headers=admin)
    assert r.status_code == 409


@pytest.mark.parametrize("cambio", [{"tipo": "XX"}, {"base": "NADA"}, {"alicuota": -1}, {"alicuota": 101},
                                    {"vigente_desde": "2026-05-01", "vigente_hasta": "2026-01-01"}])
def test_valida_el_impuesto(client, admin, cambio):
    assert client.post("/api/configuraciones/impuestos", json={**IVA, **cambio}, headers=admin).status_code == 422


def test_editar_no_puede_pisar_el_codigo_de_otro(client, admin):
    client.post("/api/configuraciones/impuestos", json=IVA, headers=admin)
    otro = client.post("/api/configuraciones/impuestos", json={**IVA, "codigo": "IVA105", "alicuota": 10.5},
                       headers=admin).json()
    r = client.put(f"/api/configuraciones/impuestos/{otro['id']}", json={**IVA, "codigo": "IVA21"}, headers=admin)
    assert r.status_code == 409
    r = client.put(f"/api/configuraciones/impuestos/{otro['id']}",
                   json={**IVA, "codigo": "IVA105", "alicuota": 10.5, "nombre": "IVA reducido"}, headers=admin)
    assert r.status_code == 200 and r.json()["nombre"] == "IVA reducido"


def test_baja_y_reactivar_filtran_los_activos(client, admin):
    i = client.post("/api/configuraciones/impuestos", json=IVA, headers=admin).json()
    client.post(f"/api/configuraciones/impuestos/{i['id']}/baja", headers=admin)
    assert client.get("/api/configuraciones/impuestos?estado=activos", headers=admin).json()["total"] == 0
    assert client.get("/api/configuraciones/impuestos", headers=admin).json()["total"] == 1
    client.post(f"/api/configuraciones/impuestos/{i['id']}/reactivar", headers=admin)
    assert client.get("/api/configuraciones/impuestos?estado=activos", headers=admin).json()["total"] == 1


def test_inexistente_es_404(client, admin):
    assert client.put("/api/configuraciones/impuestos/99", json=IVA, headers=admin).status_code == 404
    assert client.post("/api/configuraciones/indices/99/baja", headers=admin).status_code == 404


def test_escribir_sin_permiso_es_403(client, lector):
    assert client.get("/api/configuraciones/impuestos", headers=lector).status_code == 200
    r = client.post("/api/configuraciones/impuestos", json=IVA, headers=lector)
    assert r.status_code == 403 and "impuestos:write" in r.json()["detail"]
    assert client.post("/api/configuraciones/indices", json={"codigo": "X", "nombre": "X"}, headers=lector).status_code == 403


def test_permiso_de_otro_catalogo_no_alcanza(client):
    """Tener `indices:write` no habilita a escribir impuestos."""
    from tests.conftest import gateway
    h = gateway("indices:write", "impuestos:read")
    assert client.post("/api/configuraciones/impuestos", json=IVA, headers=h).status_code == 403
    assert client.post("/api/configuraciones/indices", json={"codigo": "TPM", "nombre": "TPM"}, headers=h).status_code == 201


def test_abm_de_indices(client, admin):
    r = client.post("/api/configuraciones/indices", headers=admin, json={
        "codigo": "badlar", "nombre": "BADLAR", "valor": 45.5, "fuente": "BCRA", "fecha_valor": "2026-09-01"})
    assert r.status_code == 201 and r.json()["codigo"] == "BADLAR"
    iid = r.json()["id"]
    r = client.put(f"/api/configuraciones/indices/{iid}", headers=admin,
                   json={"codigo": "BADLAR", "nombre": "BADLAR privados", "valor": 47})
    assert r.json()["valor"] == 47.0
    assert client.post("/api/configuraciones/indices", headers=admin,
                       json={"codigo": "BADLAR", "nombre": "dup"}).status_code == 409
    client.post(f"/api/configuraciones/indices/{iid}/baja", headers=admin)
    assert client.get("/api/configuraciones/indices?estado=activos", headers=admin).json()["items"] == []
