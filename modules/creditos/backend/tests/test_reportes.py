"""Reportería PDF: recibo de cobranza."""
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


def test_recibo_pdf(client):
    h = _auth(client)
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "120000", "cantidad_cuotas": 6,
        "fecha_primer_vencimiento": "2026-01-10",
    }).json()
    cred = client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()
    recibo = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1], "fecha_pago": "2026-02-15",
    }).json()

    r = client.get(f"/api/creditos/caja/recibos/{recibo['id']}/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"           # firma de archivo PDF
    assert len(r.content) > 1000              # tiene contenido real


def _otorgar_y_cobrar(client, h):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "120000", "cantidad_cuotas": 6,
        "fecha_primer_vencimiento": "2026-03-10",
    }).json()
    cred = client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()
    client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1], "fecha_pago": "2026-03-10"})
    return cred


def test_libro_diario_pdf(client):
    h = _auth(client)
    _otorgar_y_cobrar(client, h)
    r = client.get("/api/creditos/contabilidad/libro-diario/pdf", headers=h)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_cierre_pdf(client):
    h = _auth(client)
    _otorgar_y_cobrar(client, h)
    r = client.get("/api/creditos/caja/cierre/pdf?fecha=2026-03-10", headers=h)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_envios_excel(client):
    h = _auth(client)
    _otorgar_y_cobrar(client, h)
    r = client.get("/api/creditos/creditos/consultas/envios/excel?desde=2026-01-01&hasta=2026-12-31",
                   headers=h)
    assert r.status_code == 200
    # firma de archivo XLSX (zip: 'PK')
    assert r.content[:2] == b"PK"
    assert "spreadsheet" in r.headers["content-type"]


def test_iva_periodo(client):
    from decimal import Decimal
    h = _auth(client)
    _otorgar_y_cobrar(client, h)  # cobranza -> genera IVA débito en el asiento
    r = client.get("/api/creditos/contabilidad/iva-periodo?desde=2026-01-01&hasta=2026-12-31",
                   headers=h).json()
    assert Decimal(r["iva_debito"]) > 0
    assert r["cantidad_asientos"] >= 1
    # PDF
    p = client.get("/api/creditos/contabilidad/iva-periodo/pdf?desde=2026-01-01&hasta=2026-12-31",
                   headers=h)
    assert p.status_code == 200 and p.content[:4] == b"%PDF"


def test_pendientes_de_cobro(client):
    h = _auth(client)
    _otorgar_y_cobrar(client, h)  # paga cuota 1; quedan pendientes
    # a fin de año todas las cuotas restantes están vencidas
    r = client.get("/api/creditos/caja/pendientes-cobro?fecha_corte=2026-12-31", headers=h).json()
    assert r["cantidad"] >= 1
    assert float(r["total"]) > 0
    # con días de atraso hay mora en al menos una
    assert any(i["dias_mora"] > 0 for i in r["items"])
    # PDF
    p = client.get("/api/creditos/caja/pendientes-cobro/pdf?fecha_corte=2026-12-31", headers=h)
    assert p.status_code == 200 and p.content[:4] == b"%PDF"


def test_control_de_caja(client):
    from decimal import Decimal
    h = _auth(client)
    _otorgar_y_cobrar(client, h)  # cobra en 2026-03-10 con el usuario admin
    r = client.get("/api/creditos/caja/control?fecha=2026-03-10", headers=h).json()
    assert r["cantidad_total"] >= 1
    assert Decimal(r["total_general"]) > 0
    assert any(c["cajero"] == "admin" for c in r["cajeros"])
    p = client.get("/api/creditos/caja/control/pdf?fecha=2026-03-10", headers=h)
    assert p.status_code == 200 and p.content[:4] == b"%PDF"


def test_cartera_pdf(client):
    h = _auth(client)
    _otorgar_y_cobrar(client, h)
    p = client.get("/api/creditos/creditos/consultas/estadisticas/pdf", headers=h)
    assert p.status_code == 200 and p.content[:4] == b"%PDF"
