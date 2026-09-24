"""Anexo de resolución (el vínculo con Créditos) y expedientes con sus pases.

Las solicitudes viven en Créditos: acá se prueba el circuito contra su API interna, simulada por el
fixture `creditos` (ver conftest).
"""
from datetime import date

import pytest


@pytest.fixture
def solicitudes(creditos):
    """Solicitudes aprobadas y cubicadas, que es lo que entra al anexo."""
    return creditos.alta


def test_el_anexo_ofrece_las_aprobadas_del_producto(client, h, solicitudes):
    """El anexo se arma por producto; sin producto, trae todo lo pendiente de otorgar."""
    solicitudes(3, producto="prod-personal")
    solicitudes(2, producto="prod-vivienda")
    personal = client.get("/api/despacho/anexo/solicitudes?tipo=prod-personal", headers=h).json()
    assert personal["cantidad"] == 3

    vivienda = client.get("/api/despacho/anexo/solicitudes?tipo=prod-vivienda", headers=h).json()
    assert vivienda["cantidad"] == 2

    todas = client.get("/api/despacho/anexo/solicitudes", headers=h).json()
    assert todas["cantidad"] == 5


def test_los_tipos_de_anexo_son_los_productos_de_creditos(client, h):
    d = client.get("/api/despacho/anexo/tipos", headers=h).json()
    assert d[0] == {"tipo": "", "nombre": "Todos los productos"}
    assert {"tipo": "prod-vivienda", "nombre": "Vivienda"} in d


def test_no_ofrece_las_que_no_estan_aprobadas(client, h, solicitudes):
    solicitudes(2, estado="EN_EVALUACION")
    d = client.get("/api/despacho/anexo/solicitudes", headers=h).json()
    assert d["cantidad"] == 0


def test_asignar_pone_el_numero_de_la_resolucion_en_las_solicitudes(client, h, resolucion, solicitudes):
    r = resolucion()
    ss = solicitudes(3)
    a = client.post("/api/despacho/anexo/asignar", headers=h,
                    json={"tipo": "", "resolucion_id": r["id"],
                          "solicitud_ids": [s["id"] for s in ss]})
    assert a.status_code == 200
    assert a.json()["asignadas"] == 3 and a.json()["numero"] == r["numero"]

    # Ya no aparecen como candidatas, y sí al pedir el lote (para reimprimir).
    assert client.get("/api/despacho/anexo/solicitudes", headers=h).json()["cantidad"] == 0
    d = client.get(f"/api/despacho/anexo/solicitudes?lote={r['numero']}", headers=h).json()
    assert d["cantidad"] == 3 and d["items"][0]["numero_resolucion"] == r["numero"]


def test_una_solicitud_no_entra_en_dos_resoluciones(client, h, resolucion, solicitudes):
    r1, r2 = resolucion(), resolucion()
    ss = solicitudes(2)
    client.post("/api/despacho/anexo/asignar", headers=h,
                json={"tipo": "", "resolucion_id": r1["id"], "solicitud_ids": [s["id"] for s in ss]})
    otra = client.post("/api/despacho/anexo/asignar", headers=h,
                       json={"tipo": "", "resolucion_id": r2["id"], "solicitud_ids": [ss[0]["id"]]})
    assert otra.status_code == 422 and "otra resolución" in otra.json()["detail"]


def test_no_se_saca_una_solicitud_de_un_acto_ya_emitido(client, h, resolucion, solicitudes):
    r = resolucion()
    ss = solicitudes(1)
    client.post("/api/despacho/anexo/asignar", headers=h,
                json={"tipo": "", "resolucion_id": r["id"], "solicitud_ids": [ss[0]["id"]]})
    # Mientras es borrador, se puede corregir.
    assert client.post("/api/despacho/anexo/quitar", headers=h,
                       json={"solicitud_ids": [ss[0]["id"]],
                             "numero_resolucion": r["numero"]}).status_code == 200

    client.post("/api/despacho/anexo/asignar", headers=h,
                json={"tipo": "", "resolucion_id": r["id"], "solicitud_ids": [ss[0]["id"]]})
    client.post(f"/api/despacho/resoluciones/{r['id']}/firmar", headers=h)
    no = client.post("/api/despacho/anexo/quitar", headers=h,
                     json={"solicitud_ids": [ss[0]["id"]], "numero_resolucion": r["numero"]})
    assert no.status_code == 422 and "emitido" in no.json()["detail"]


def test_si_creditos_no_responde_la_pantalla_lo_dice(client, h, monkeypatch):
    """Una lista vacía se confundiría con 'no hay nada para otorgar'."""
    from fastapi import HTTPException

    from app.services import creditos_central

    def caido(**kw):
        raise HTTPException(503, "Créditos no responde; probá de nuevo en un momento.")

    monkeypatch.setattr(creditos_central, "candidatas", caido)
    r = client.get("/api/despacho/anexo/solicitudes", headers=h)
    assert r.status_code == 503 and "no responde" in r.json()["detail"]


def test_el_anexo_se_imprime_en_word(client, h, resolucion, solicitudes):
    r = resolucion()
    ss = solicitudes(2)
    client.post("/api/despacho/anexo/asignar", headers=h,
                json={"tipo": "", "resolucion_id": r["id"], "solicitud_ids": [s["id"] for s in ss]})
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
