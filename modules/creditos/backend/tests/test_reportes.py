"""Reportería del circuito de créditos: recibo en PDF, pendientes de cobro, envíos y cartera."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _otorgar(client, h, primer_vto="2026-03-10"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "120000", "cantidad_cuotas": 6,
        "fecha_primer_vencimiento": primer_vto,
    }).json()
    return client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()


def test_recibo_pdf(client):
    """El recibo de la cancelación anticipada (Cancelación de crédito) se imprime en PDF."""
    h = _auth(client)
    cred = _otorgar(client, h, primer_vto="2026-01-10")
    recibo = client.post(f"/api/creditos/creditos/{cred['id']}/cancelar", headers=h,
                         json={"fecha_pago": "2026-02-15"}).json()

    r = client.get(f"/api/creditos/caja/recibos/{recibo['id']}/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"           # firma de archivo PDF
    assert len(r.content) > 1000              # tiene contenido real


def test_envios_excel(client):
    h = _auth(client)
    _otorgar(client, h)
    r = client.get("/api/creditos/creditos/consultas/envios/excel?desde=2026-01-01&hasta=2026-12-31",
                   headers=h)
    assert r.status_code == 200
    # firma de archivo XLSX (zip: 'PK')
    assert r.content[:2] == b"PK"
    assert "spreadsheet" in r.headers["content-type"]


def test_pendientes_de_cobro(client):
    h = _auth(client)
    _otorgar(client, h)
    # a fin de año todas las cuotas están vencidas
    r = client.get("/api/creditos/caja/pendientes-cobro?fecha_corte=2026-12-31", headers=h).json()
    assert r["cantidad"] >= 1
    assert float(r["total"]) > 0
    # con días de atraso hay mora en al menos una
    assert any(i["dias_mora"] > 0 for i in r["items"])
    # PDF
    p = client.get("/api/creditos/caja/pendientes-cobro/pdf?fecha_corte=2026-12-31", headers=h)
    assert p.status_code == 200 and p.content[:4] == b"%PDF"


def test_cartera_pdf(client):
    h = _auth(client)
    _otorgar(client, h)
    p = client.get("/api/creditos/creditos/consultas/estadisticas/pdf", headers=h)
    assert p.status_code == 200 and p.content[:4] == b"%PDF"
