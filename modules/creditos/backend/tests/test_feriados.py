"""Maestro de feriados por país + su efecto en el motor de cronograma."""
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


def test_seed_feriados_ar_presente(client):
    h = _auth(client)
    import datetime
    a = datetime.date.today().year
    r = client.get(f"/api/creditos/feriados?pais=AR&anio={a}", headers=h)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    fechas = {i["fecha"] for i in items}
    assert f"{a}-01-01" in fechas and f"{a}-12-25" in fechas  # fijos sembrados
    assert len(items) >= 8


def test_paises_disponibles(client):
    h = _auth(client)
    cods = {p["codigo"] for p in client.get("/api/creditos/feriados/paises", headers=h).json()["items"]}
    assert "AR" in cods and "UY" in cods


def test_crear_manual_y_duplicado(client):
    h = _auth(client)
    d = {"pais": "AR", "fecha": "2030-06-17", "nombre": "Feriado de prueba", "tipo": "PUENTE"}
    r = client.post("/api/creditos/feriados", headers=h, json=d)
    assert r.status_code == 201 and r.json()["origen"] == "MANUAL"
    # duplicado (mismo país+fecha) → 409
    assert client.post("/api/creditos/feriados", headers=h, json=d).status_code == 409


def test_importar_ar(client):
    """Importar un año carga el calendario (fuente oficial si hay red, o cálculo local)."""
    h = _auth(client)
    r = client.post("/api/creditos/feriados/importar", headers=h, json={"pais": "AR", "anio": 2031})
    assert r.status_code == 200, r.text
    assert r.json()["totalFuente"] >= 8
    nombres = {i["nombre"] for i in client.get("/api/creditos/feriados?pais=AR&anio=2031", headers=h).json()["items"]}
    assert "Año Nuevo" in nombres


def test_calculo_local_ar_tipos():
    """Cálculo local (sin red, determinístico): fija el tipo que colorea la UI."""
    from datetime import date
    from app.api.feriados import _ar_calculados, _pascua
    filas = {n: (f, t) for f, n, t in _ar_calculados(2031)}
    # Pascua 2031 = 13-abr → Carnaval lunes 24-feb, Viernes Santo 11-abr.
    assert _pascua(2031) == date(2031, 4, 13)
    assert filas["Año Nuevo"] == (date(2031, 1, 1), "INAMOVIBLE")
    assert filas["Carnaval (lunes)"] == (date(2031, 2, 24), "TRASLADABLE")
    assert filas["Viernes Santo"] == (date(2031, 4, 11), "TRASLADABLE")


def test_seed_ar_tipos_correctos(client):
    """El seed usa el cálculo local: Año Nuevo queda INAMOVIBLE (color rojo en la UI)."""
    h = _auth(client)
    import datetime
    a = datetime.date.today().year
    items = client.get(f"/api/creditos/feriados?pais=AR&anio={a}", headers=h).json()["items"]
    an = next(i for i in items if i["nombre"] == "Año Nuevo")
    assert an["tipo"] == "INAMOVIBLE"


def test_preview_respeta_feriado_del_maestro(client):
    """El motor saltea un feriado del maestro (uno movible, no de los fijos) al fechar un vencimiento."""
    _auth(client)  # dispara el lifespan que siembra el calendario AR
    from datetime import date
    from app.core.database import SessionLocal
    from app.api.productos import _feriados_engine
    from app.services.productos_calc import cronograma
    with SessionLocal() as db:
        # Feriado MOVIBLE cargado a mano (no está en FERIADOS_FIJOS del motor): sólo el maestro lo conoce.
        db.add(models_feriado(db, "AR", date(2027, 6, 10), "Puente de prueba"))
        db.commit()
        fset = _feriados_engine(db)
        assert date(2027, 6, 10) in fset
        # Un vencimiento que caería el 2027-06-10 debe rodar al día hábil siguiente (11).
        f = cronograma("FRANCES", 100000, 1, 52, fecha_valor=date(2027, 5, 10), dia_pago=10,
                       primer_venc_dias=31, ajuste_fin_semana="SIGUIENTE_HABIL", feriados=fset)
        assert str(f[0]["fecha_vencimiento"]) == "2027-06-11", str(f[0]["fecha_vencimiento"])


def models_feriado(db, pais, fecha, nombre):
    from app import models
    return models.Feriado(pais=pais, fecha=fecha, nombre=nombre, tipo="PUENTE", origen="MANUAL", activo=True)
