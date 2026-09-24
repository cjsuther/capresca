"""Resoluciones y disposiciones: numeración, ciclo de vida y export a Word."""
from datetime import date

import pytest


# --------------------------------------------------------------------------- numeración
def test_el_correlativo_es_por_ano_y_tipo(client, h, resolucion):
    """Resoluciones y disposiciones llevan series distintas, y cada una arranca en 1 cada año."""
    r1 = resolucion()
    r2 = resolucion()
    d1 = resolucion(tipo="DIS")

    assert (r1["numero"], r1["tipo"]) == (1, "RES")
    assert (r2["numero"], r2["tipo"]) == (2, "RES")
    assert (d1["numero"], d1["tipo"]) == (1, "DIS")      # la disposición no continúa la serie de RES

    vieja = resolucion(fecha="2024-05-10")
    assert (vieja["numero"], vieja["anio"]) == (1, 2024)  # otro año, otra serie


def test_no_se_puede_crear_un_tipo_que_no_existe(client, h):
    r = client.post("/api/despacho/resoluciones", headers=h, json={"tipo": "XX", "asunto": "x"})
    assert r.status_code == 422 and "RES" in r.json()["detail"]


# --------------------------------------------------------------------------- modelos
def test_el_modelo_aporta_el_motivo_y_el_cuerpo(client, h, modelo, resolucion):
    """Al elegir 'Modelo a utilizar', su descripción pasa a ser el motivo del acto y su plantilla,
    el texto inicial que después se edita."""
    m = modelo(descripcion="TRANSFERENCIA", plantilla="<p>VISTO: el expediente…</p>")
    r = resolucion(modelo_id=m["id"])

    assert r["motivo"] == "TRANSFERENCIA" and r["motivo_codigo"] == m["codigo"]
    assert r["texto"] == "<p>VISTO: el expediente…</p>"
    assert r["asunto"] == "Otorgamiento de créditos"     # el asunto explícito no se pisa


def test_si_no_se_escribe_asunto_se_usa_el_motivo(client, h, modelo):
    m = modelo(descripcion="BAJA DE AFILIADO")
    r = client.post("/api/despacho/resoluciones", headers=h,
                    json={"tipo": "RES", "modelo_id": m["id"]}).json()
    assert r["asunto"] == "BAJA DE AFILIADO"


def test_el_texto_escrito_le_gana_a_la_plantilla(client, h, modelo, resolucion):
    m = modelo(plantilla="<p>plantilla</p>")
    r = resolucion(modelo_id=m["id"], texto="<p>lo que escribió el operador</p>")
    assert r["texto"] == "<p>lo que escribió el operador</p>"


def test_un_modelo_inexistente_se_rechaza(client, h):
    r = client.post("/api/despacho/resoluciones", headers=h,
                    json={"tipo": "RES", "asunto": "x", "modelo_id": 999})
    assert r.status_code == 422


# --------------------------------------------------------------------------- ciclo de vida
def test_el_borrador_se_edita(client, h, resolucion):
    r = resolucion()
    assert r["estado"] == "B"
    e = client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h,
                   json={"texto": "<p>nuevo</p>", "importe": 150000.5, "origen": "EXP 123/2026"})
    assert e.status_code == 200
    assert e.json()["texto"] == "<p>nuevo</p>" and float(e.json()["importe"]) == 150000.5
    assert e.json()["origen"] == "EXP 123/2026"


def test_lo_ya_emitido_no_se_toca(client, h, resolucion):
    """Un acto firmado o con N° real es inmutable: no se altera algo ya emitido."""
    r = resolucion()
    client.post(f"/api/despacho/resoluciones/{r['id']}/firmar", headers=h)
    e = client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h, json={"texto": "otro"})
    assert e.status_code == 422 and "emitido" in e.json()["detail"]


def test_no_se_cambia_el_ano_de_una_resolucion(client, h, resolucion):
    """Rompería la serie del correlativo, que es por año y tipo."""
    r = resolucion()
    e = client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h, json={"fecha": "2020-01-05"})
    assert e.status_code == 422 and "año" in e.json()["detail"]


def test_no_se_firma_dos_veces(client, h, resolucion):
    r = resolucion()
    assert client.post(f"/api/despacho/resoluciones/{r['id']}/firmar", headers=h).status_code == 200
    segunda = client.post(f"/api/despacho/resoluciones/{r['id']}/firmar", headers=h)
    assert segunda.status_code == 422


# --------------------------------------------------------------------------- número real
def test_el_numero_real_tiene_su_propia_serie(client, h, resolucion):
    """El oficial llega después del correlativo y lleva su propia numeración por año y tipo."""
    r1, r2 = resolucion(), resolucion()
    a = client.post(f"/api/despacho/resoluciones/{r2['id']}/numero-real", headers=h,
                    json={"fecha_real": "2026-09-24"}).json()
    b = client.post(f"/api/despacho/resoluciones/{r1['id']}/numero-real", headers=h,
                    json={"fecha_real": "2026-09-25"}).json()

    # El orden del número real es el de la carga, no el del correlativo.
    assert (a["numero"], a["numero_real"]) == (2, 1)
    assert (b["numero"], b["numero_real"]) == (1, 2)
    assert a["estado"] == "F" and a["fecha_real"] == "2026-09-24"


def test_el_numero_real_se_carga_una_sola_vez(client, h, resolucion):
    r = resolucion()
    client.post(f"/api/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={})
    otra = client.post(f"/api/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={})
    assert otra.status_code == 422 and "N° real" in otra.json()["detail"]


# --------------------------------------------------------------------------- anulación
def test_anular_no_borra(client, h, resolucion):
    """Como en el papel: el acto queda con su número y el motivo de la anulación."""
    r = resolucion()
    a = client.post(f"/api/despacho/resoluciones/{r['id']}/anular", headers=h,
                    json={"motivo": "Error en el importe"})
    assert a.status_code == 200
    assert a.json()["anulada"] is True and a.json()["motivo_anulacion"] == "Error en el importe"
    assert a.json()["numero"] == r["numero"]

    # Y no se puede seguir trabajando sobre ella.
    assert client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h,
                      json={"texto": "x"}).status_code == 422
    assert client.post(f"/api/despacho/resoluciones/{r['id']}/firmar", headers=h).status_code == 422


def test_la_anulacion_pide_motivo(client, h, resolucion):
    r = resolucion()
    assert client.post(f"/api/despacho/resoluciones/{r['id']}/anular", headers=h,
                       json={"motivo": "  "}).status_code == 422


# --------------------------------------------------------------------------- beneficiarios
def test_los_beneficiarios_se_reemplazan_completos(client, h, resolucion):
    """La grilla se edita entera, como en la pantalla."""
    r = resolucion(beneficiarios=[{"nro_doc": "30111222", "nombre": "PEREZ JUAN", "importe": 1000},
                                  {"nro_doc": "27222333", "nombre": "GOMEZ ANA", "importe": 2000}])
    assert len(r["beneficiarios"]) == 2

    e = client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h,
                   json={"beneficiarios": [{"nro_doc": "20999888", "nombre": "SOLO UNO"}]}).json()
    assert [b["nombre"] for b in e["beneficiarios"]] == ["SOLO UNO"]


# --------------------------------------------------------------------------- listado y Word
def test_el_listado_filtra_y_pagina(client, h, resolucion):
    for _ in range(3):
        resolucion()
    resolucion(tipo="DIS")
    firmada = resolucion()
    client.post(f"/api/despacho/resoluciones/{firmada['id']}/firmar", headers=h)

    todas = client.get("/api/despacho/resoluciones", headers=h).json()
    assert todas["total"] == 5 and len(todas["items"]) == 5

    solo_dis = client.get("/api/despacho/resoluciones?tipo=DIS", headers=h).json()
    assert solo_dis["total"] == 1

    borradores = client.get("/api/despacho/resoluciones?estado=B", headers=h).json()
    assert borradores["total"] == 4

    pagina = client.get("/api/despacho/resoluciones?pagina=2&por_pagina=2", headers=h).json()
    assert len(pagina["items"]) == 2 and pagina["pagina"] == 2


def test_el_word_sale_con_el_numero_que_corresponde(client, h, resolucion):
    """Mientras no tenga el oficial, el papel circula con el correlativo."""
    r = resolucion(texto="<h1>RESOLUCIÓN</h1><p>VISTO: el expediente…</p>")
    w = client.get(f"/api/despacho/resoluciones/{r['id']}/word", headers=h)
    assert w.status_code == 200
    assert w.headers["content-disposition"].endswith(f'RES_{r["numero"]}_{r["anio"]}.docx"')
    assert w.content[:2] == b"PK"        # un .docx es un zip

    client.post(f"/api/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={})
    w2 = client.get(f"/api/despacho/resoluciones/{r['id']}/word", headers=h)
    assert 'RES_1_' in w2.headers["content-disposition"]


# --------------------------------------------------------------------------- permisos
def test_leer_no_alcanza_para_escribir(client, solo_lectura):
    assert client.get("/api/despacho/resoluciones", headers=solo_lectura).status_code == 200
    r = client.post("/api/despacho/resoluciones", headers=solo_lectura, json={"asunto": "x"})
    assert r.status_code == 403 and "resoluciones:write" in r.json()["detail"]


def test_sin_identidad_del_gateway_no_se_entra(client):
    assert client.get("/api/despacho/resoluciones").status_code == 401
