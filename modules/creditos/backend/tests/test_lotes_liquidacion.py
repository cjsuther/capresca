"""Lotes de liquidación: por producto + día, numerados por año y con tope configurable."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import models, models_productos as m
from app.core.database import SessionLocal
from app.services import lotes_liquidacion


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _producto(client, h, codigo):
    with SessionLocal() as db:
        return db.query(m.PPProducto).filter_by(codigo=codigo).one().id


def _originar(client, h, producto_id, nombre):
    c = client.post("/api/creditos/contratos/originar", headers=h, json={
        "producto_id": producto_id, "cliente_nombre": nombre, "monto": 300_000, "plazo": 12,
        "desembolsar": False}).json()
    assert c["estado"] == "A_LIQUIDAR", c
    return c["id"]


def _tope(n):
    with SessionLocal() as db:
        p = db.query(models.Parametro).filter_by(clave=lotes_liquidacion.PARAMETRO).first()
        p.valor = str(n)
        db.commit()


def _lotes(client, h):
    return client.get("/api/creditos/contratos/lotes-liquidacion", headers=h).json()


def _lote_de(lotes, contrato_id):
    return next(lt for lt in lotes["items"] if any(c["id"] == contrato_id for c in lt["contratos"]))


def test_un_lote_por_producto_y_dia_numerado_en_el_anio(client):
    h = _auth(client)
    pers, adel = _producto(client, h, "LP-PERS-01"), _producto(client, h, "LP-JUB-01")
    a1, a2 = _originar(client, h, pers, "SOSA LUIS"), _originar(client, h, pers, "RIOS EVA")
    b1 = _originar(client, h, adel, "PAZ ANA")

    d = _lotes(client, h)
    anio = date.today().year
    lote_pers, lote_adel = _lote_de(d, a1), _lote_de(d, b1)
    assert _lote_de(d, a2)["id"] == lote_pers["id"]
    assert lote_pers["id"] != lote_adel["id"]
    assert (lote_pers["codigo"], lote_adel["codigo"]) == (f"{anio}-0001", f"{anio}-0002")
    assert lote_pers["productoId"] == pers and lote_pers["fecha"] == date.today().isoformat()
    assert (lote_pers["cantidad"], lote_pers["ocupados"], lote_pers["maximo"]) == (2, 2, 50)
    # Persistido: el contrato queda ligado a su lote en la DB.
    with SessionLocal() as db:
        assert db.get(m.PPContrato, a1).lote_liquidacion_id == lote_pers["id"]


def test_lleno_el_lote_se_abre_el_siguiente_numero(client):
    h = _auth(client)
    _tope(2)
    pers = _producto(client, h, "LP-PERS-01")
    ids = [_originar(client, h, pers, f"CLIENTE {i}") for i in range(5)]

    d = _lotes(client, h)
    codigos = [_lote_de(d, i)["codigo"] for i in ids]
    anio = date.today().year
    assert codigos == [f"{anio}-0001"] * 2 + [f"{anio}-0002"] * 2 + [f"{anio}-0003"]
    assert d["maximo"] == 2


def test_el_numero_arranca_en_uno_cada_anio(client):
    h = _auth(client)
    pers = _producto(client, h, "LP-PERS-01")
    anio = date.today().year
    with SessionLocal() as db:
        db.add(m.PPLoteLiquidacion(anio=anio - 1, numero=37, producto_id=pers, fecha=date(anio - 1, 12, 30)))
        db.commit()
    cid = _originar(client, h, pers, "SOSA LUIS")
    assert _lote_de(_lotes(client, h), cid)["codigo"] == f"{anio}-0001"


def test_liquidar_un_lote_no_toca_los_otros(client):
    h = _auth(client)
    pers, adel = _producto(client, h, "LP-PERS-01"), _producto(client, h, "LP-JUB-01")
    a = _originar(client, h, pers, "SOSA LUIS")
    b = _originar(client, h, adel, "PAZ ANA")
    lote_a = _lote_de(_lotes(client, h), a)

    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"lote_id": lote_a["id"]}).json()
    assert r["lote"] == lote_a["codigo"] and r["total"] == 1
    with SessionLocal() as db:
        assert db.get(m.PPContrato, a).estado == "ACTIVO"
        assert db.get(m.PPContrato, b).estado == "A_LIQUIDAR"
    assert [lt["id"] for lt in _lotes(client, h)["items"]] == [_lote_de(_lotes(client, h), b)["id"]]


def test_liquidar_un_lote_inexistente_es_404(client):
    h = _auth(client)
    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"lote_id": 999})
    assert r.status_code == 404


def test_los_a_liquidar_sin_lote_se_ubican_al_listar(client):
    """Los originados antes de los lotes numerados no quedan fuera de la pantalla."""
    h = _auth(client)
    pers = _producto(client, h, "LP-PERS-01")
    cid = _originar(client, h, pers, "SOSA LUIS")
    with SessionLocal() as db:
        db.get(m.PPContrato, cid).lote_liquidacion_id = None
        db.query(m.PPLoteLiquidacion).delete()
        db.commit()
    assert _lote_de(_lotes(client, h), cid)["codigo"] == f"{date.today().year}-0001"


def test_el_tope_se_siembra_en_los_parametros_de_creditos(client):
    with SessionLocal() as db:
        p = db.query(models.Parametro).filter_by(clave="LOTE_LIQUIDACION_MAX").one()
        assert (p.valor, p.ambito) == ("50", "creditos")
