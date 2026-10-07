"""Órdenes de pago de Tesorería: juntan resoluciones / disposiciones con sus lotes; el lote queda
PARA_LIQUIDAR y, acreditadas todas sus transferencias, LIQUIDADO."""
import pytest
from fastapi.testclient import TestClient

from app import models, models_productos as m
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services import lotes_liquidacion as lotes
from tests.test_lotes_liquidacion import (CLAVE as CLAVE_DESPACHO, _aprobada, _asignar, _auth, _lote,
                                          _producto, _sol)

CLAVE = "clave-tesoreria-test"
HT = {"X-Api-Key": CLAVE}
OP = "/internal/creditos/ordenes-pago"
AVISO = "/internal/creditos/tesoreria/resultado"


@pytest.fixture()
def client(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "despacho_internal_api_key", CLAVE_DESPACHO)
    monkeypatch.setattr(s, "tesoreria_internal_api_key", CLAVE)
    from app.main import app
    with TestClient(app) as c:
        yield c


def _con_resolucion(client, montos=(300_000, 200_000), id=7, numero=45, oficial=120, producto=None):
    pid = producto or _producto()
    sids = [_aprobada(pid, mt) for mt in montos]
    lid = _sol(sids[0]).lote_liquidacion_id
    assert _asignar(client, [lid], id=id, numero=numero, oficial=oficial).status_code == 200
    return lid, sids


def _reservar(client, actos, orden_id=1, codigo="OP-2026-00001"):
    return client.post(f"{OP}/reservar", headers=HT,
                       json={"orden_id": orden_id, "codigo": codigo, "usuario": "tesorero", "actos": actos})


def _aviso(client, contratos, estado="CONFIRMADO", referencia="OP-2026-00001", lote="LOT-2026-00009"):
    return client.post(AVISO, headers=HT, json={"lote": lote, "referencia_origen": referencia, "simulado": True,
                                                "pagos": [{"referencia_externa": c, "estado": estado} for c in contratos]})


def _contratos(lid):
    with SessionLocal() as db:
        return [c.id for c in db.query(m.PPContrato).filter_by(lote_liquidacion_id=lid).all()]


def test_sin_la_clave_de_tesoreria_no_se_entra(client):
    assert client.get(f"{OP}/disponibles").status_code == 401


def test_disponibles_agrupa_por_resolucion_y_solo_lotes_con_resolucion(client):
    lid, _ = _con_resolucion(client)
    _aprobada(_producto("LP-JUB-01"))                           # lote abierto: no aparece
    d = client.get(f"{OP}/disponibles", headers=HT).json()["items"]
    assert len(d) == 1
    assert d[0]["acto"]["clave"] == "id:7" and d[0]["acto"]["numeroOficial"] == 120
    assert [x["id"] for x in d[0]["lotes"]] == [lid] and d[0]["total"] == 500_000


def test_la_orden_origina_y_deja_el_lote_para_liquidar(client):
    lid, sids = _con_resolucion(client)
    r = _reservar(client, ["id:7"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["lotes"] == [_lote(lid).codigo] and len(d["pagos"]) == 2 and d["total"] == 500_000
    assert all(len(p["cbu"]) == 22 and p["concepto"].startswith("OP-2026-00001") for p in d["pagos"])
    lt = _lote(lid)
    assert lt.estado == "PARA_LIQUIDAR" and lt.orden_pago_id == 1 and lt.orden_pago_codigo == "OP-2026-00001"
    with SessionLocal() as db:
        for sid in sids:
            s = db.get(m.PPSolicitud, sid)
            c = db.get(m.PPContrato, s.contrato_id)
            assert s.estado == "ORIGINADA" and c.estado == "A_LIQUIDAR"
            assert c.datos_adicionales["desembolso"]["estado"] == "EN_TESORERIA"
            assert c.datos_adicionales["desembolso"]["orden_pago"] == "OP-2026-00001"
    assert client.get(f"{OP}/disponibles", headers=HT).json()["items"] == []


def test_reservar_dos_veces_la_misma_orden_devuelve_lo_mismo(client):
    _con_resolucion(client)
    a = _reservar(client, ["id:7"]).json()
    b = _reservar(client, ["id:7"]).json()
    assert sorted(p["referencia_externa"] for p in a["pagos"]) == sorted(p["referencia_externa"] for p in b["pagos"])


def test_un_lote_no_entra_en_dos_ordenes(client):
    _con_resolucion(client)
    assert _reservar(client, ["id:7"]).status_code == 200
    r = _reservar(client, ["id:7"], orden_id=2, codigo="OP-2026-00002")
    assert r.status_code == 409 and "ya no tienen lotes disponibles" in r.json()["detail"]


def test_varias_resoluciones_en_una_orden(client):
    la, _ = _con_resolucion(client)
    lb, _ = _con_resolucion(client, (100_000,), id=8, numero=46, oficial=121, producto=_producto("LP-JUB-01"))
    r = _reservar(client, ["id:7", "id:8"])
    assert r.status_code == 200 and sorted(r.json()["lotes"]) == sorted([_lote(la).codigo, _lote(lb).codigo])
    assert len(r.json()["actos"]) == 2


def test_sin_numero_oficial_no_se_paga(client):
    lid, _ = _con_resolucion(client, oficial=None)
    r = _reservar(client, ["id:7"])
    assert r.status_code == 409 and "N° oficial" in r.json()["detail"]
    assert _lote(lid).estado == "CON_RESOLUCION"


def test_si_algo_no_se_puede_liquidar_no_entra_nada(client):
    lid, _ = _con_resolucion(client)
    with SessionLocal() as db:
        db.get(models.Cliente, 1).cbu = "123"
        db.commit()
    r = _reservar(client, ["id:7"])
    assert r.status_code == 409 and "no se puede armar completa" in r.json()["detail"]
    assert _lote(lid).estado == "CON_RESOLUCION" and _lote(lid).orden_pago_id is None


def test_acreditadas_todas_el_lote_queda_liquidado(client):
    lid, _ = _con_resolucion(client)
    _reservar(client, ["id:7"])
    c1, c2 = _contratos(lid)
    r = _aviso(client, [c1])
    assert r.status_code == 200 and r.json()["lotesLiquidados"] == []
    assert _lote(lid).estado == "PARA_LIQUIDAR"
    r = _aviso(client, [c2])
    assert r.json()["lotesLiquidados"] == [_lote(lid).codigo]
    assert _lote(lid).estado == "LIQUIDADO" and _lote(lid).liquidado_en is not None


def test_una_transferencia_fallida_deja_el_credito_observado(client):
    lid, _ = _con_resolucion(client)
    _reservar(client, ["id:7"])
    c1, c2 = _contratos(lid)
    r = _aviso(client, [c1], estado="FALLIDO")
    assert r.json()["observados"]
    with SessionLocal() as db:
        assert db.get(m.PPContrato, c1).datos_adicionales["desembolso"]["estado"] == "OBSERVADO"
    _aviso(client, [c1, c2])                       # Tesorería la reintentó y se acreditó
    assert _lote(lid).estado == "LIQUIDADO"


def test_anular_la_orden_devuelve_los_lotes_y_otra_orden_los_reusa(client):
    lid, sids = _con_resolucion(client)
    _reservar(client, ["id:7"])
    r = client.post(f"{OP}/liberar", headers=HT, json={"orden_id": 1})
    assert r.status_code == 200 and _lote(lid).estado == "CON_RESOLUCION" and _lote(lid).orden_pago_id is None
    antes = sorted(_contratos(lid))
    r = _reservar(client, ["id:7"], orden_id=2, codigo="OP-2026-00002")
    assert r.status_code == 200 and sorted(_contratos(lid)) == antes          # no se originan de nuevo
    assert _lote(lid).orden_pago_codigo == "OP-2026-00002"


def test_con_algo_acreditado_la_orden_no_se_anula(client):
    lid, _ = _con_resolucion(client)
    _reservar(client, ["id:7"])
    _aviso(client, _contratos(lid)[:1])
    r = client.post(f"{OP}/liberar", headers=HT, json={"orden_id": 1})
    assert r.status_code == 409 and _lote(lid).estado == "PARA_LIQUIDAR"


def test_un_lote_en_orden_de_pago_no_se_toca(client):
    h = _auth(client)
    lid, sids = _con_resolucion(client)
    _reservar(client, ["id:7"])
    r = client.post("/api/creditos/contratos/lotes-liquidacion/mover", headers=h,
                    json={"solicitud_id": sids[0], "nuevo": True})
    assert r.status_code == 409 and "orden de pago" in r.json()["detail"]
    r = client.post(f"/internal/creditos/lotes/{lid}/quitar-resolucion", headers={"X-Api-Key": CLAVE_DESPACHO})
    assert r.status_code == 409 and "orden de pago" in r.json()["detail"]
    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"lote_id": lid})
    assert r.status_code == 409 and "lo paga Tesorería" in r.json()["detail"]


def test_con_tesoreria_el_lote_no_se_liquida_desde_creditos(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "desembolso_via_tesoreria", True)
    h = _auth(client)
    lid, _ = _con_resolucion(client)
    r = client.post("/api/creditos/contratos/liquidar-lote", headers=h, json={"lote_id": lid})
    assert r.status_code == 409 and "orden de pago" in r.json()["detail"]


def test_el_tipo_del_acto_viaja_con_el_lote(client):
    lid, _ = _con_resolucion(client)
    from tests.test_lotes_liquidacion import HD, _res
    client.post("/internal/creditos/lotes/resolucion", headers=HD, json={**_res(oficial=120), "tipo": "DIS"})
    assert _lote(lid).resolucion_tipo == "DIS"
    d = client.get(f"{OP}/disponibles", headers=HT).json()["items"]
    assert d[0]["acto"]["tipo"] == "DIS"
    assert lotes.PARA_LIQUIDAR in lotes.ORDEN
