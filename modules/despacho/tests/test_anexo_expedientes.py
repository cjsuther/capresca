"""Lotes de créditos con su resolución (el vínculo con Créditos) y expedientes con sus pases.

Los lotes viven en Créditos: acá se prueba el circuito contra su API interna, simulada por el
fixture `creditos` (ver conftest).
"""
from datetime import date

import pytest


def _asignar(client, h, r, lotes):
    return client.post("/api/despacho/lotes/asignar", headers=h,
                       json={"resolucion_id": r["id"], "lote_ids": [lt["id"] for lt in lotes]})


def test_despacho_ve_los_lotes_de_creditos(client, h, creditos):
    a = creditos.alta()
    creditos.alta(producto="prod-vivienda")
    d = client.get("/api/despacho/lotes", headers=h).json()
    assert d["cantidad"] == 2
    personal = client.get("/api/despacho/lotes?tipo=prod-personal", headers=h).json()
    assert [x["id"] for x in personal["items"]] == [a["id"]]
    tipos = client.get("/api/despacho/lotes/tipos", headers=h).json()
    assert tipos[0] == {"tipo": "", "nombre": "Todos los tipos"} and len(tipos) == 3


def test_una_resolucion_otorga_varios_lotes_sin_pasar_su_importe(client, h, resolucion, creditos):
    r = resolucion(importe=500000)
    a, b = creditos.alta((100000, 200000)), creditos.alta((150000,))
    ok = _asignar(client, h, r, [a, b])
    assert ok.status_code == 200, ok.text
    d = ok.json()
    assert d["asignados"] == [a["codigo"], b["codigo"]] and float(d["disponible"]) == 50000
    assert creditos.lotes[a["id"]]["estado"] == "CON_RESOLUCION"
    assert creditos.lotes[a["id"]]["resolucion"]["id"] == r["id"]

    c = creditos.alta((60000,))
    no = _asignar(client, h, r, [c])                       # 450 + 60 > 500
    assert no.status_code == 409 and "supera el importe" in no.json()["detail"]

    comp = client.get(f"/api/despacho/resoluciones/{r['id']}/lotes", headers=h).json()
    assert float(comp["total"]) == 450000 and float(comp["disponible"]) == 50000 and len(comp["lotes"]) == 2


def test_sin_importe_la_resolucion_no_otorga_lotes(client, h, resolucion, creditos):
    r = resolucion()
    no = _asignar(client, h, r, [creditos.alta()])
    assert no.status_code == 422 and "importe" in no.json()["detail"]


def test_a_un_acto_emitido_no_se_le_agregan_ni_sacan_lotes(client, h, resolucion, creditos):
    r = resolucion(importe=1000000)
    a = creditos.alta()
    _asignar(client, h, r, [a])
    client.post(f"/api/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={"numero_real": 55})
    assert _asignar(client, h, r, [creditos.alta()]).status_code == 422
    no = client.post(f"/api/despacho/lotes/{a['id']}/quitar-resolucion", headers=h)
    assert no.status_code == 422 and "emitido" in no.json()["detail"]


def test_quitar_la_resolucion_de_un_lote(client, h, resolucion, creditos):
    r = resolucion(importe=1000000)
    a = creditos.alta()
    _asignar(client, h, r, [a])
    ok = client.post(f"/api/despacho/lotes/{a['id']}/quitar-resolucion", headers=h)
    assert ok.status_code == 200 and creditos.lotes[a["id"]]["estado"] == "ABIERTO"


def test_los_lotes_migrados_se_vinculan_a_su_resolucion(client, h, resolucion, creditos):
    r = resolucion(importe=1000000)
    a = creditos.alta(resolucion={"id": None, "numero": r["numero"], "anio": r["anio"]})
    d = client.get("/api/despacho/lotes", headers=h).json()
    assert d["items"][0]["resolucion_despacho"]["id"] == r["id"]
    assert creditos.lotes[a["id"]]["resolucion"]["id"] == r["id"]           # Créditos ya conoce el id


def test_si_creditos_no_responde_la_pantalla_lo_dice(client, h, monkeypatch):
    from fastapi import HTTPException

    from app.services import creditos_central

    def caido(**_kw):
        raise HTTPException(503, "Créditos no responde; probá de nuevo en un momento.")

    monkeypatch.setattr(creditos_central, "lotes", caido)
    r = client.get("/api/despacho/lotes", headers=h)
    assert r.status_code == 503 and "Créditos no responde" in r.json()["detail"]


def test_el_anexo_se_imprime_en_word_con_las_solicitudes_de_sus_lotes(client, h, resolucion, creditos):
    r = resolucion(importe=1000000)
    _asignar(client, h, r, [creditos.alta(), creditos.alta((50000,))])
    w = client.get(f"/api/despacho/anexo/word/{r['id']}", headers=h)
    assert w.status_code == 200 and w.content[:2] == b"PK"


# --------------------------------------------------------------------------- expedientes
def test_el_alta_deja_el_primer_pase(client, h):
    e = client.post("/api/despacho/expedientes", headers=h,
                    json={"numero": "EXP-1/2026", "caratula": "Solicitud de crédito",
                          "iniciador": "PEREZ JUAN", "oficina": "MESA DE ENTRADAS"})
    assert e.status_code == 201
    d = e.json()
    assert d["oficina_actual"] == "MESA DE ENTRADAS" and len(d["pases"]) == 1
    assert d["pases"][0]["motivo"] == "Alta del expediente"


def test_el_numero_de_expediente_no_se_repite(client, h):
    datos = {"numero": "EXP-9/2026", "caratula": "x"}
    assert client.post("/api/despacho/expedientes", headers=h, json=datos).status_code == 201
    assert client.post("/api/despacho/expedientes", headers=h, json=datos).status_code == 409


def test_los_pases_arman_el_recorrido(client, h):
    e = client.post("/api/despacho/expedientes", headers=h,
                    json={"numero": "EXP-2/2026", "caratula": "Pase a pase",
                          "oficina": "MESA DE ENTRADAS"}).json()
    p = client.post(f"/api/despacho/expedientes/{e['id']}/pase", headers=h,
                    json={"oficina_destino": "DESPACHO", "motivo": "Para dictamen"}).json()
    assert p["oficina_actual"] == "DESPACHO"
    assert [x["oficina_destino"] for x in p["pases"]] == ["MESA DE ENTRADAS", "DESPACHO"]

    # No se pasa a la oficina donde ya está.
    igual = client.post(f"/api/despacho/expedientes/{e['id']}/pase", headers=h,
                        json={"oficina_destino": "DESPACHO"})
    assert igual.status_code == 422


def test_un_expediente_archivado_no_circula(client, h):
    e = client.post("/api/despacho/expedientes", headers=h,
                    json={"numero": "EXP-3/2026", "caratula": "Fin", "oficina": "DESPACHO"}).json()
    a = client.post(f"/api/despacho/expedientes/{e['id']}/archivar", headers=h).json()
    assert a["estado"] == "A" and a["oficina_actual"] == "ARCHIVO"
    assert client.post(f"/api/despacho/expedientes/{e['id']}/pase", headers=h,
                       json={"oficina_destino": "MESA"}).status_code == 422


def test_el_tablero_cuenta_por_oficina(client, h):
    for i, of in enumerate(("DESPACHO", "DESPACHO", "LEGALES")):
        client.post("/api/despacho/expedientes", headers=h,
                    json={"numero": f"EXP-1{i}/2026", "caratula": "x", "oficina": of})
    tablero = {x["oficina"]: x["cantidad"] for x in
               client.get("/api/despacho/expedientes-por-oficina", headers=h).json()}
    assert tablero == {"DESPACHO": 2, "LEGALES": 1}
