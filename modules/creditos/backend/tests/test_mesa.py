"""Módulo Mesa de entradas: turnos de atención."""
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


def _tipo(client, h):
    return client.get("/api/creditos/mesa/tipos-tramite", headers=h).json()[0]["id"]


def test_generar_turnos_correlativos(client):
    h = _auth(client)
    tt = _tipo(client, h)
    t1 = client.post("/api/creditos/mesa/turnos", headers=h, json={
        "tipo_tramite_id": tt, "cliente_nombre": "PEREZ", "fecha": "2026-06-01"}).json()
    t2 = client.post("/api/creditos/mesa/turnos", headers=h, json={
        "tipo_tramite_id": tt, "cliente_nombre": "GOMEZ", "fecha": "2026-06-01"}).json()
    assert t2["numero"] == t1["numero"] + 1
    assert t1["estado"] == "E"


def test_flujo_llamar_atender(client):
    h = _auth(client)
    tt = _tipo(client, h)
    for nom in ("A", "B", "C"):
        client.post("/api/creditos/mesa/turnos", headers=h, json={
            "tipo_tramite_id": tt, "cliente_nombre": nom, "fecha": "2026-06-02"})

    # llamar siguiente (FIFO) -> el primero
    llamado = client.post("/api/creditos/mesa/llamar", headers=h, json={
        "box": "Box 1", "fecha": "2026-06-02"}).json()
    assert llamado["cliente_nombre"] == "A"
    assert llamado["estado"] == "L"
    assert llamado["box"] == "Box 1"

    # atender
    at = client.post(f"/api/creditos/mesa/turnos/{llamado['id']}/atender", headers=h).json()
    assert at["estado"] == "A"

    # tablero: 2 en espera, 0 llamados, 1 atendido
    tab = client.get("/api/creditos/mesa/tablero?fecha=2026-06-02", headers=h).json()
    assert len(tab["en_espera"]) == 2
    assert tab["atendidos"] == 1


def test_cancelar_y_no_llamar_vacio(client):
    h = _auth(client)
    tt = _tipo(client, h)
    t = client.post("/api/creditos/mesa/turnos", headers=h, json={
        "tipo_tramite_id": tt, "fecha": "2026-06-03"}).json()
    c = client.post(f"/api/creditos/mesa/turnos/{t['id']}/cancelar", headers=h).json()
    assert c["estado"] == "C"
    # no quedan turnos en espera -> 404
    r = client.post("/api/creditos/mesa/llamar", headers=h, json={"box": "Box 1", "fecha": "2026-06-03"})
    assert r.status_code == 404


def _sembrar_tramite(**kw):
    import datetime
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    if not db.query(models.TramiteTipo).filter_by(codigo="N").first():
        db.add(models.TramiteTipo(codigo="N", descripcion="NOTA", corta="NOTA"))
    db.add(models.Tramite(tipo="N", letra="S", numero=1062, anio=2011, sentido="I",
        referencia="SOLICITUD X", iniciador="LEIVA SEVERA", asegurado="LEIVA SEVERA",
        estado="A", oficina_actual=2, hojas=3,
        fecha_alta=datetime.date(2011, 5, 10)))
    db.commit(); db.close()


def test_consulta_tramites(client):
    h = _auth(client)
    _sembrar_tramite()
    tipos = client.get("/api/creditos/mesa/tramites/tipos", headers=h).json()
    assert any(t["codigo"] == "N" for t in tipos)
    r = client.get("/api/creditos/mesa/tramites?tipo=N", headers=h).json()
    assert r["total"] >= 1
    t = r["items"][0]
    assert t["expediente"].startswith("N S-1062/2011")
    assert t["estado"] == "En trámite"
    # búsqueda
    r2 = client.get("/api/creditos/mesa/tramites?q=LEIVA", headers=h).json()
    assert r2["total"] >= 1


def test_solo_expedientes(client):
    h = _auth(client)
    import datetime
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.Tramite(tipo="E1", letra="A", numero=1, anio=2020, sentido="I",
        referencia="EXP SEGURO", estado="A", fecha_alta=datetime.date(2020, 1, 1)))
    db.add(models.Tramite(tipo="N", letra="B", numero=2, anio=2020, sentido="I",
        referencia="NOTA", estado="A", fecha_alta=datetime.date(2020, 1, 2)))
    db.commit(); db.close()
    r = client.get("/api/creditos/mesa/tramites?solo_expedientes=true", headers=h).json()
    assert all(t["tipo"].startswith("E") for t in r["items"])
    assert any(t["expediente"].startswith("E1") for t in r["items"])


def test_tramites_ingresados(client):
    h = _auth(client)
    _sembrar_tramite()
    r = client.get("/api/creditos/mesa/tramites/ingresados", headers=h).json()
    assert r["total"] >= 1
    assert any(f["tipo"] == "N" and f["descripcion"] == "NOTA" for f in r["por_tipo"])


def test_pases_de_tramite(client):
    h = _auth(client)
    import datetime
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    t = models.Tramite(tipo="E1", letra="R", numero=967, anio=2012, sentido="I",
                       referencia="SEGURO VIDA", estado="A")
    db.add(t); db.flush()
    db.add(models.TramitePase(tipo="E1", letra="R", numero=967, anio=2012,
        fecha_pase=datetime.date(2012, 3, 1), oficina_origen=9, oficina_destino=2,
        texto="Pase inicial", activo=False))
    db.add(models.TramitePase(tipo="E1", letra="R", numero=967, anio=2012,
        fecha_pase=datetime.date(2012, 3, 5), oficina_origen=2, oficina_destino=5,
        texto="A resolución", activo=True))
    db.commit(); tid = t.id; db.close()
    r = client.get(f"/api/creditos/mesa/tramites/{tid}/pases", headers=h).json()
    assert r["cantidad"] == 2
    assert r["expediente"] == "E1 R-967/2012"
    # sin oficinas sembradas, se muestra "Of. N"
    assert r["pases"][0]["oficina_destino"] == "Of. 2"
    assert r["pases"][1]["orden"] == 2
    # trámite inexistente -> 404
    assert client.get("/api/creditos/mesa/tramites/99999999/pases", headers=h).status_code == 404


def test_oficinas_y_pases_con_nombre(client):
    h = _auth(client)
    import datetime
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.Oficina(id=9, denominacion="MESA DE ENTRADAS", interna=True))
    db.add(models.Oficina(id=2, denominacion="IN - AUDITORIA GENERAL", interna=True))
    t = models.Tramite(tipo="N", letra="X", numero=5, anio=2020, sentido="I", estado="A")
    db.add(t); db.flush()
    db.add(models.TramitePase(tipo="N", letra="X", numero=5, anio=2020,
        fecha_pase=datetime.date(2020, 1, 2), oficina_origen=9, oficina_destino=2,
        texto="pase", activo=True))
    db.commit(); tid = t.id; db.close()
    ofs = client.get("/api/creditos/mesa/oficinas", headers=h).json()
    assert any(o["id"] == 9 and o["denominacion"] == "MESA DE ENTRADAS" for o in ofs)
    r = client.get(f"/api/creditos/mesa/tramites/{tid}/pases", headers=h).json()
    assert r["pases"][0]["oficina_origen"] == "MESA DE ENTRADAS"
    assert r["pases"][0]["oficina_destino"] == "IN - AUDITORIA GENERAL"
