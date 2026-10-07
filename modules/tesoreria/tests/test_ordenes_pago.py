"""Órdenes de pago de créditos: resoluciones / disposiciones con sus lotes, pagadas por un lote de pagos."""
import pytest
from fastapi import HTTPException

from app import models
from app.services import creditos_central
from tests.conftest import gateway, pago

ARMADOR = gateway("lotes:read", "lotes:write", username="ana", user_id=8)


class CreditosFalso:
    """Créditos: dos resoluciones con lotes; reservar devuelve una transferencia por crédito."""
    def __init__(self):
        self.actos = {
            "id:7": {"acto": {"clave": "id:7", "tipo": "RES", "numero": 45, "anio": 2026, "numeroOficial": 120},
                     "lotes": [{"id": 1, "codigo": "2026-0001"}],
                     "pagos": [pago("cto-1", 300000), pago("cto-2", 200000, beneficiario="GOMEZ ANA")]},
            "id:8": {"acto": {"clave": "id:8", "tipo": "DIS", "numero": 12, "anio": 2026, "numeroOficial": 30},
                     "lotes": [{"id": 2, "codigo": "2026-0002"}], "pagos": [pago("cto-3", 100000)]},
        }
        self.reservas, self.liberadas, self.caido, self.rechazo = {}, [], False, None

    def disponibles(self):
        tomados = {a for r in self.reservas.values() for a in r}
        return {"items": [{k: v for k, v in g.items() if k != "pagos"} for c, g in self.actos.items() if c not in tomados]}

    def reservar(self, orden_id, codigo, usuario, actos):
        if self.caido:
            raise HTTPException(503, "Créditos no responde")
        if self.rechazo:
            raise HTTPException(409, self.rechazo)
        tomados = {a for oid, r in self.reservas.items() if oid != orden_id for a in r}
        if set(actos) & tomados:
            raise HTTPException(409, "Estas resoluciones / disposiciones ya no tienen lotes disponibles")
        self.reservas[orden_id] = list(actos)
        grupos = [self.actos[a] for a in actos]
        return {"pagos": [dict(p, concepto=f"{codigo} {p['concepto']}") for g in grupos for p in g["pagos"]],
                "lotes": [lt["codigo"] for g in grupos for lt in g["lotes"]],
                "actos": [{k: v for k, v in g.items() if k != "pagos"} for g in grupos]}

    def liberar(self, orden_id):
        if self.caido:
            raise HTTPException(503, "Créditos no responde")
        self.reservas.pop(orden_id, None)
        self.liberadas.append(orden_id)
        return {"lotes": []}


@pytest.fixture(autouse=True)
def creditos(monkeypatch):
    f = CreditosFalso()
    for nombre in ("disponibles", "reservar", "liberar"):
        monkeypatch.setattr(creditos_central, nombre, getattr(f, nombre))
    return f


def _confeccionar(client, actos=("id:7",), h=ARMADOR):
    return client.post("/api/tesoreria/ordenes-pago", headers=h, json={"actos": list(actos)})


def test_lista_las_resoluciones_con_lotes_disponibles(client):
    d = client.get("/api/tesoreria/ordenes-pago/disponibles", headers=ARMADOR).json()
    assert [g["acto"]["clave"] for g in d["items"]] == ["id:7", "id:8"]


def test_confeccionar_crea_la_orden_y_su_lote_de_pagos(client, db, creditos):
    r = _confeccionar(client, ("id:7", "id:8"))
    assert r.status_code == 201, r.text
    op = r.json()
    assert op["codigo"].startswith("OP-") and op["codigo"].endswith("-00001") and op["estado"] == "CONFECCIONADA"
    assert op["cantidad"] == 3 and op["importe"] == 600000 and op["estado_pago"] == "PARA_APROBAR"
    assert op["actos_texto"] == "Res. 120/2026, Disp. 30/2026" and op["lotes"] == ["2026-0001", "2026-0002"]
    lote = db.get(models.Lote, op["lote"]["id"])
    assert lote.origen == "CREDITOS" and lote.referencia_origen == op["codigo"] and lote.creado_por == "ana"
    assert lote.callback_url.endswith("/internal/creditos/tesoreria/resultado")
    assert {p.referencia_externa for p in lote.pagos} == {"cto-1", "cto-2", "cto-3"}
    assert creditos.reservas[op["id"]] == ["id:7", "id:8"]
    assert client.get("/api/tesoreria/ordenes-pago/disponibles", headers=ARMADOR).json()["items"] == []


def test_la_numeracion_es_correlativa(client):
    a = _confeccionar(client, ("id:7",)).json()
    b = _confeccionar(client, ("id:8",)).json()
    assert int(b["codigo"][-5:]) == int(a["codigo"][-5:]) + 1


def test_un_acto_no_entra_en_dos_ordenes(client, db):
    _confeccionar(client, ("id:7",))
    r = _confeccionar(client, ("id:7",))
    assert r.status_code == 409 and "ya no tienen lotes" in r.json()["detail"]
    assert db.query(models.OrdenPago).count() == 1          # la fallida no queda


def test_si_creditos_rechaza_no_queda_nada(client, db, creditos):
    creditos.rechazo = "La orden de pago no se puede armar completa. Lote 2026-0001 · SOL-1: falta CBU"
    r = _confeccionar(client)
    assert r.status_code == 409 and "falta CBU" in r.json()["detail"]
    assert db.query(models.OrdenPago).count() == 0 and db.query(models.Lote).count() == 0


def test_si_un_pago_ya_esta_en_otro_lote_se_deshace_la_reserva(client, db, creditos, lote_creditos):
    lote_creditos(pagos=[pago("cto-1", 300000)])                     # cto-1 ya va en otro lote vivo
    r = _confeccionar(client)
    assert r.status_code == 409 and "ya está en el lote" in r.json()["detail"]
    assert creditos.liberadas and db.query(models.OrdenPago).count() == 0


def test_sin_permiso_de_carga_no_se_confecciona(client):
    r = _confeccionar(client, h=gateway("lotes:read"))
    assert r.status_code == 403


def test_los_pagos_de_una_orden_no_se_excluyen(client, teso):
    op = _confeccionar(client).json()
    lote = client.get(f"/api/tesoreria/lotes/{op['lote']['id']}", headers=teso).json()
    assert lote["orden_pago"]["codigo"] == op["codigo"]
    r = client.post(f"/api/tesoreria/lotes/{lote['id']}/pagos/{lote['pagos'][0]['id']}/excluir", headers=teso,
                    json={"motivo": "no"})
    assert r.status_code == 409 and "no se excluyen" in r.json()["detail"]


def test_el_tesorero_aprueba_y_paga_la_orden(client, teso, origen):
    op = _confeccionar(client).json()
    lid = op["lote"]["id"]
    assert client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso).status_code == 200
    assert client.get(f"/api/tesoreria/ordenes-pago/{op['id']}", headers=teso).json()["estado_pago"] == "PARA_PAGAR"
    assert client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso, json={}).status_code == 200
    client.post(f"/api/tesoreria/lotes/{lid}/actualizar", headers=teso)            # simulación: se acreditan
    d = client.get(f"/api/tesoreria/ordenes-pago/{op['id']}", headers=teso).json()
    assert d["estado_pago"] == "PAGADA" and all(p["estado"] == "CONFIRMADO" for p in d["pagos"])
    assert not d["puede_anular"]
    url, _h, cuerpo = origen.recibidos[-1]
    assert cuerpo["referencia_origen"] == op["codigo"] and {p["estado"] for p in cuerpo["pagos"]} == {"CONFIRMADO"}


def test_anular_antes_de_pagar_libera_los_lotes(client, db, creditos):
    op = _confeccionar(client).json()
    r = client.post(f"/api/tesoreria/ordenes-pago/{op['id']}/anular", headers=ARMADOR, json={"motivo": "Error de carga"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "ANULADA" and r.json()["estado_pago"] == "ANULADA"
    assert creditos.liberadas == [op["id"]]
    lote = db.get(models.Lote, op["lote"]["id"])
    assert lote.estado == "RECHAZADO" and all(p.estado == "RECHAZADO" for p in lote.pagos)
    # el acto vuelve a estar disponible para otra orden
    assert _confeccionar(client).status_code == 201


def test_sin_motivo_o_sin_creditos_no_se_anula(client, db, creditos):
    op = _confeccionar(client).json()
    r = client.post(f"/api/tesoreria/ordenes-pago/{op['id']}/anular", headers=ARMADOR, json={"motivo": ""})
    assert r.status_code == 422
    creditos.caido = True
    r = client.post(f"/api/tesoreria/ordenes-pago/{op['id']}/anular", headers=ARMADOR, json={"motivo": "x"})
    assert r.status_code == 503
    assert db.get(models.OrdenPago, op["id"]).estado == "CONFECCIONADA"


def test_enviada_no_se_anula(client, teso):
    op = _confeccionar(client).json()
    lid = op["lote"]["id"]
    client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso)
    client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso, json={})
    r = client.post(f"/api/tesoreria/ordenes-pago/{op['id']}/anular", headers=teso, json={"motivo": "x"})
    assert r.status_code == 409 and "ya se empezó a pagar" in r.json()["detail"]


def test_rechazar_el_lote_de_una_orden_la_anula(client, db, teso, creditos):
    op = _confeccionar(client).json()
    r = client.post(f"/api/tesoreria/lotes/{op['lote']['id']}/rechazar", headers=teso, json={"motivo": "Montos mal"})
    assert r.status_code == 200, r.text
    assert db.get(models.OrdenPago, op["id"]).estado == "ANULADA" and creditos.liberadas == [op["id"]]


def test_lista_las_ordenes(client):
    _confeccionar(client, ("id:7",))
    _confeccionar(client, ("id:8",))
    d = client.get("/api/tesoreria/ordenes-pago", headers=ARMADOR).json()["items"]
    assert [x["actos_texto"] for x in d] == ["Disp. 30/2026", "Res. 120/2026"]
