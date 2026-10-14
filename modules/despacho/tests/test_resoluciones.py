"""Resoluciones y disposiciones: numeración, ciclo de vida y export a Word."""
from datetime import date

import pytest


# --------------------------------------------------------------------------- numeración
def test_el_correlativo_es_por_ano_y_serie(client, h, resolucion):
    """Cada serie (el área que emite) numera por su cuenta y arranca en 1 cada año."""
    r1 = resolucion()
    r2 = resolucion()
    d1 = resolucion(tipo="DIS")

    assert (r1["numero"], r1["serie"]) == (1, 1)
    assert (r2["numero"], r2["serie"]) == (2, 1)
    # Dentro de una serie, la disposición sigue el mismo correlativo que la resolución: así viene la
    # numeración del sistema anterior.
    assert (d1["numero"], d1["tipo"]) == (3, "DIS")

    seguros = resolucion(serie=4)
    assert (seguros["numero"], seguros["serie_nombre"]) == (1, "Seguros")

    vieja = resolucion(fecha="2024-05-10")
    assert (vieja["numero"], vieja["anio"]) == (1, 2024)  # otro año, otra numeración


# --------------------------------------------------------------------------- desde qué número sigue
def _fijar(client, h, anio, serie=1, **datos):
    return client.put(f"/api/despacho/numeracion/{anio}/{serie}", headers=h, json=datos)


def test_la_numeracion_sigue_desde_el_numero_fijado(client, h, resolucion):
    """La numeración continúa la del sistema anterior: el correlativo y el oficial siguen desde ahí."""
    anio = date.today().year
    r = _fijar(client, h, anio, desde_numero=1500, desde_oficial=870)
    assert r.status_code == 200, r.text
    assert (r.json()["proximoNumero"], r.json()["proximoOficial"]) == (1500, 870)
    a, b = resolucion(), resolucion()
    assert (a["numero"], b["numero"]) == (1500, 1501)
    of = client.post(f"/api/despacho/resoluciones/{a['id']}/numero-real", headers=h, json={}).json()
    assert of["numero_real"] == 870
    assert resolucion(serie=4)["numero"] == 1               # las otras series siguen por su cuenta


def test_no_se_puede_fijar_un_numero_ya_usado(client, h, resolucion):
    anio = date.today().year
    resolucion(); resolucion()                                # correlativos 1 y 2
    r = _fijar(client, h, anio, desde_numero=2)
    assert r.status_code == 422 and "mayor que 2" in r.json()["detail"]
    assert _fijar(client, h, anio, desde_numero=0).status_code == 422
    assert _fijar(client, h, anio, desde_numero=3).status_code == 200


def test_la_pantalla_de_numeracion_muestra_ultimo_y_proximo(client, h, resolucion):
    anio = date.today().year
    resolucion()
    _fijar(client, h, anio, serie=4, desde_numero=900)
    filas = {x["serie"]: x for x in client.get(f"/api/despacho/numeracion?anio={anio}", headers=h).json()}
    assert (filas[1]["ultimoNumero"], filas[1]["proximoNumero"], filas[1]["desdeNumero"]) == (1, 2, None)
    assert (filas[4]["ultimoNumero"], filas[4]["proximoNumero"], filas[4]["desdeNumero"]) == (None, 900, 900)
    assert filas[4]["actualizadoPor"] == "despacho"


def test_fijar_la_numeracion_pide_el_permiso_de_firmar(client, solo_lectura):
    from tests.conftest import gateway
    r = client.put(f"/api/despacho/numeracion/{date.today().year}/1",
                   headers=gateway("resoluciones:read", "resoluciones:write"), json={"desde_numero": 10})
    assert r.status_code == 403


def test_la_serie_tiene_que_existir(client, h):
    r = client.post("/api/despacho/resoluciones", headers=h, json={"asunto": "x", "serie": 99})
    assert r.status_code == 422 and "serie 99" in r.json()["detail"]


def test_las_series_se_publican_para_los_combos(client, h):
    r = client.get("/api/despacho/series", headers=h)
    assert r.status_code == 200
    series = {x["serie"]: x["nombre"] for x in r.json()}
    assert series[1].startswith("General") and series[4] == "Seguros"


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
    """Rompería el correlativo, que corre por año y serie."""
    r = resolucion()
    e = client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h, json={"fecha": "2020-01-05"})
    assert e.status_code == 422 and "año" in e.json()["detail"]


def test_no_se_firma_dos_veces(client, h, resolucion):
    r = resolucion()
    assert client.post(f"/api/despacho/resoluciones/{r['id']}/firmar", headers=h).status_code == 200
    segunda = client.post(f"/api/despacho/resoluciones/{r['id']}/firmar", headers=h)
    assert segunda.status_code == 422


# --------------------------------------------------------------------------- número real
def test_el_numero_real_tiene_su_propia_numeracion(client, h, resolucion):
    """El oficial llega después del correlativo y lleva su propia numeración por año y serie."""
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



def test_el_numero_oficial_se_escribe_a_mano_y_no_se_repite(client, h, resolucion):
    r1, r2 = resolucion(), resolucion()
    a = client.post(f"/api/despacho/resoluciones/{r1['id']}/numero-real", headers=h, json={"numero_real": 120})
    assert a.status_code == 200 and a.json()["numero_real"] == 120
    rep = client.post(f"/api/despacho/resoluciones/{r2['id']}/numero-real", headers=h, json={"numero_real": 120})
    assert rep.status_code == 409 and "ya lo tiene otra" in rep.json()["detail"]
    assert client.post(f"/api/despacho/resoluciones/{r2['id']}/numero-real", headers=h,
                       json={"numero_real": 0}).status_code == 422           # sólo números positivos
    assert client.post(f"/api/despacho/resoluciones/{r2['id']}/numero-real", headers=h,
                       json={"numero_real": "12a"}).status_code == 422


def test_el_numero_oficial_y_la_fecha_se_corrigen_aun_emitida(client, h, resolucion, creditos):
    r = resolucion()
    client.post(f"/api/despacho/resoluciones/{r['id']}/numero-real", headers=h, json={"numero_real": 7})
    c = client.put(f"/api/despacho/resoluciones/{r['id']}/oficial", headers=h,
                   json={"numero_real": 8, "fecha": f"{r['anio']}-03-15"})
    assert c.status_code == 200, c.text
    d = c.json()
    assert d["numero_real"] == 8 and d["fecha"] == f"{r['anio']}-03-15"
    assert d["creado_en"] == r["creado_en"]                       # la fecha de creación queda
    assert creditos.avisos[-1]["numero_oficial"] == 8 and creditos.avisos[-1]["fecha"] == f"{r['anio']}-03-15"
    otro_anio = client.put(f"/api/despacho/resoluciones/{r['id']}/oficial", headers=h,
                           json={"fecha": f"{r['anio'] - 1}-12-31"})
    assert otro_anio.status_code == 422


def test_el_importe_no_baja_de_lo_que_otorgan_sus_lotes(client, h, resolucion, creditos):
    r = resolucion(importe=500000)
    a = creditos.alta((100000, 200000))
    client.post("/api/despacho/lotes/asignar", headers=h, json={"resolucion_id": r["id"], "lote_ids": [a["id"]]})
    no = client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h, json={"importe": 250000})
    assert no.status_code == 409
    assert client.get(f"/api/despacho/resoluciones/{r['id']}", headers=h).json()["importe"] in ("500000.00", 500000, "500000")
    ok = client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h, json={"importe": 300000})
    assert ok.status_code == 200


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


# --------------------------------------------------------------------------- sector, actividad, baja
def test_el_acto_hereda_sector_y_actividad_del_modelo(client, h):
    m = client.post("/api/despacho/modelos", headers=h,
                    json={"descripcion": "OTORGAMIENTO", "tipo": "RES", "sector": "Créditos",
                          "actividad": "Préstamos"}).json()
    heredado = client.post("/api/despacho/resoluciones", headers=h,
                           json={"tipo": "RES", "modelo_id": m["id"]}).json()
    assert (heredado["sector"], heredado["actividad"]) == ("Créditos", "Préstamos")
    propio = client.post("/api/despacho/resoluciones", headers=h,
                         json={"tipo": "RES", "modelo_id": m["id"], "sector": "Seguros"}).json()
    assert (propio["sector"], propio["actividad"]) == ("Seguros", "Préstamos")

    e = client.put(f"/api/despacho/resoluciones/{propio['id']}", headers=h, json={"actividad": "Siniestros"})
    assert e.json()["actividad"] == "Siniestros"
    assert client.get("/api/despacho/resoluciones?sector=Seguros", headers=h).json()["total"] == 1
    assert client.get("/api/despacho/clasificacion", headers=h).json() == {
        "sectores": ["Créditos", "Seguros"], "actividades": ["Préstamos", "Siniestros"]}


def test_inactivar_saca_el_acto_del_listado_y_lo_congela(client, h, resolucion):
    r = resolucion()
    i = client.post(f"/api/despacho/resoluciones/{r['id']}/activa", headers=h, json={"activo": False})
    assert i.status_code == 200 and i.json()["activa"] is False

    assert client.get("/api/despacho/resoluciones", headers=h).json()["total"] == 0
    assert client.get("/api/despacho/resoluciones?incluir_inactivas=true", headers=h).json()["total"] == 1
    for metodo, ruta, cuerpo in (("put", "", {"texto": "x"}), ("post", "/firmar", None),
                                 ("post", "/numero-real", {}), ("post", "/anular", {"motivo": "x"}),
                                 ("put", "/oficial", {"numero_real": 3})):
        resp = getattr(client, metodo)(f"/api/despacho/resoluciones/{r['id']}{ruta}", headers=h, json=cuerpo)
        assert resp.status_code == 422 and "inactiva" in resp.json()["detail"], ruta

    a = client.post(f"/api/despacho/resoluciones/{r['id']}/activa", headers=h, json={"activo": True})
    assert a.json()["activa"] is True
    assert client.put(f"/api/despacho/resoluciones/{r['id']}", headers=h, json={"texto": "x"}).status_code == 200


def test_eliminar_borra_el_acto_y_sus_beneficiarios(client, h, resolucion, db):
    from app.models import ResolucionBeneficiario
    r = resolucion(beneficiarios=[{"nro_doc": "20111222", "nombre": "PEREZ", "importe": 100}])
    assert client.delete(f"/api/despacho/resoluciones/{r['id']}", headers=h).status_code == 204
    assert client.get(f"/api/despacho/resoluciones/{r['id']}", headers=h).status_code == 404
    assert db.query(ResolucionBeneficiario).count() == 0


def test_no_se_elimina_un_acto_que_otorga_lotes(client, h, resolucion, creditos):
    r = resolucion(importe=500000)
    lote = creditos.alta((100000,))
    client.post("/api/despacho/lotes/asignar", headers=h, json={"resolucion_id": r["id"], "lote_ids": [lote["id"]]})
    no = client.delete(f"/api/despacho/resoluciones/{r['id']}", headers=h)
    assert no.status_code == 409 and lote["codigo"] in no.json()["detail"]
    client.post(f"/api/despacho/lotes/{lote['id']}/quitar-resolucion", headers=h)
    assert client.delete(f"/api/despacho/resoluciones/{r['id']}", headers=h).status_code == 204


def test_eliminar_pide_el_permiso_de_firmar(client, resolucion):
    from tests.conftest import gateway
    r = resolucion()
    redactor = gateway("resoluciones:read", "resoluciones:write")
    assert client.delete(f"/api/despacho/resoluciones/{r['id']}", headers=redactor).status_code == 403
    assert client.post(f"/api/despacho/resoluciones/{r['id']}/activa", headers=redactor,
                       json={"activo": False}).status_code == 200
