"""ABMs de configuración de Créditos: requisitos, gasistas, montos por período."""
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


def test_abm_requisitos(client):
    h = _auth(client)
    r = client.post("/api/creditos/admin/requisitos", headers=h, json={
        "descripcion": "Fotocopia de DNI", "obligatorio": True})
    assert r.status_code == 201
    assert any(x["descripcion"] == "Fotocopia de DNI"
               for x in client.get("/api/creditos/admin/requisitos", headers=h).json())


def test_abm_gasistas(client):
    h = _auth(client)
    g = client.post("/api/creditos/admin/gasistas", headers=h, json={
        "nombre": "Instituto Gas SRL", "matricula": "MG-123"})
    assert g.status_code == 201
    assert any(x["nombre"] == "Instituto Gas SRL"
               for x in client.get("/api/creditos/admin/gasistas", headers=h).json())


def test_abm_montos_periodo(client):
    h = _auth(client)
    linea = next(l for l in client.get("/api/creditos/creditos/lineas", headers=h).json()
                 if l["tipo_calculo"] == 1)
    m = client.post("/api/creditos/admin/montos-periodo", headers=h, json={
        "linea_id": linea["id"], "periodo": "2026-05", "monto_maximo": "5000000"})
    assert m.status_code == 201
    assert any(x["periodo"] == "2026-05"
               for x in client.get("/api/creditos/admin/montos-periodo", headers=h).json())


def test_abm_lineas_campos_nuevos(client):
    """ABM de Líneas (30510, /admin/lineas): alta/edición con los campos nuevos
    (plazo de gracia, paga interés en gracia, admite previo pago, cta contable) y
    baja lógica visible con incluir_inactivas."""
    h = _auth(client)
    from decimal import Decimal
    r = client.post("/api/creditos/admin/lineas", headers=h, json={
        "nombre": "LINEA TEST FRANCÉS", "cartera": 1, "tipo_calculo": 1,
        "tna": "48.00", "tasa_mora_diaria": "0.1", "plazo_max": 36, "monto_max": "500000",
        "plazo_gracia": 2, "paga_interes_gracia": True, "admite_previo_pago": True,
        "cta_contable": "1.1.1.05"})
    assert r.status_code == 201, r.text
    lid = r.json()["id"]
    assert r.json()["plazo_gracia"] == 2 and r.json()["paga_interes_gracia"] is True
    assert r.json()["cta_contable"] == "1.1.1.05"

    # el listado de créditos la ve (activa)
    assert any(l["id"] == lid for l in client.get("/api/creditos/creditos/lineas", headers=h).json())

    # edición: cambio TNA y doy de baja
    r2 = client.put(f"/api/creditos/admin/lineas/{lid}", headers=h, json={
        "nombre": "LINEA TEST FRANCÉS", "cartera": 1, "tipo_calculo": 1,
        "tna": "60.00", "plazo_max": 36, "activa": False})
    assert r2.status_code == 200 and Decimal(r2.json()["tna"]) == Decimal("60.00")

    # baja: fuera de activas, presente con incluir_inactivas
    assert not any(l["id"] == lid for l in client.get("/api/creditos/creditos/lineas", headers=h).json())
    assert any(l["id"] == lid for l in
               client.get("/api/creditos/creditos/lineas?incluir_inactivas=true", headers=h).json())


def test_turnos_generar_y_asignar(client):
    """Turnos de crédito (32065/67): genera turnos del mes distribuidos por día hábil,
    luego asigna un turno a un solicitante."""
    h = _auth(client)
    # período futuro con días hábiles; desde una fecha base para reproducibilidad
    per = "209903"  # marzo 2099
    prev = client.get("/api/creditos/creditos/turnos/generar/preview"
                      f"?periodo={per}&cantidad=50&desde=2099-02-28", headers=h).json()
    assert prev["dias_habiles"] > 0
    # total distribuido == cantidad pedida
    assert prev["total"] == 50
    assert sum(d["cantidad"] for d in prev["distribucion"]) == 50
    # turnos_por_dia = 50 // dias ; resto = 50 % dias
    assert prev["turnos_por_dia"] == 50 // prev["dias_habiles"]

    # aplicar
    r = client.post("/api/creditos/creditos/turnos/generar", headers=h,
                    json={"periodo": per, "cantidad": 50, "desde": "2099-02-28"})
    assert r.status_code == 200 and r.json()["generados"] == 50
    # no se puede regenerar (ya existen)
    assert client.post("/api/creditos/creditos/turnos/generar", headers=h,
                       json={"periodo": per, "cantidad": 50, "desde": "2099-02-28"}).status_code == 409

    # asignar el próximo turno libre
    a = client.post("/api/creditos/creditos/turnos/asignar", headers=h, json={
        "periodo": per, "cuil": "20111111112", "apellido_nombre": "PEREZ JUAN",
        "linea": 1, "sueldo": "300000"})
    assert a.status_code == 201, a.text
    assert a.json()["cuil"] == "20111111112" and a.json()["numero"] == 1

    # el turno asignado aparece en la consulta de turnos otorgados (filtrando por CUIL)
    otorgados = client.get(
        f"/api/creditos/creditos/consultas/turnos?periodo={per}&q=20111111112", headers=h).json()
    assert any(t["cuil"] == "20111111112" for t in otorgados["items"])
