"""Llegada de lotes: desde otros módulos (API interna, idempotente) y carga manual."""
from tests.conftest import gateway, pago


def test_la_api_interna_exige_la_clave(client):
    assert client.post("/internal/tesoreria/lotes", json={}).status_code == 401
    assert client.post("/internal/tesoreria/lotes", headers={"X-Api-Key": "otra"}, json={}).status_code == 401


def test_recibe_un_lote_de_creditos(client, lote_creditos, teso):
    r = lote_creditos()
    assert r["codigo"].startswith("LOT-") and r["estado"] == "PENDIENTE_APROBACION" and not r["ya_existia"]
    d = client.get(f"/api/tesoreria/lotes/{r['id']}", headers=teso).json()
    assert d["origen_nombre"] == "Créditos" and d["cantidad"] == 2 and d["total"] == 800000.0
    assert [p["estado"] for p in d["pagos"]] == ["PENDIENTE", "PENDIENTE"]
    assert d["eventos"][0]["accion"] == "ALTA"


def test_reenviar_el_mismo_lote_no_lo_duplica(client, lote_creditos, teso):
    a, b = lote_creditos(), lote_creditos()
    assert a["codigo"] == b["codigo"] and b["ya_existia"]
    assert len(client.get("/api/tesoreria/lotes", headers=teso).json()["items"]) == 1


def test_rechaza_pagos_invalidos_y_carga_el_resto(client, lote_creditos):
    r = lote_creditos(pagos=[pago("ok"), pago("cbu-malo", cbu="123"), pago("cero", monto=0),
                             pago("ok", monto=5), pago("sin-nombre", beneficiario=" ")])
    assert [p["referencia_externa"] for p in r["pagos"]] == ["ok"]
    motivos = {x["referencia_externa"]: x["motivo"] for x in r["rechazados"]}
    assert "22 dígitos" in motivos["cbu-malo"] and "mayor a cero" in motivos["cero"]
    assert "repetida" in motivos["ok"] and "beneficiario" in motivos["sin-nombre"]


def test_un_pago_no_puede_estar_vivo_en_dos_lotes(client, lote_creditos):
    lote_creditos(ref="día 1", pagos=[pago("cto-1"), pago("cto-9")])
    r = lote_creditos(ref="día 2", pagos=[pago("cto-1"), pago("cto-2")])
    assert [p["referencia_externa"] for p in r["pagos"]] == ["cto-2"]
    assert "Ya está en el lote LOT-" in r["rechazados"][0]["motivo"]


def test_sin_pagos_validos_no_se_crea(client, interna):
    r = client.post("/internal/tesoreria/lotes", headers=interna, json={
        "origen": "CREDITOS", "referencia_origen": "x", "pagos": [pago("a", cbu="1")]})
    assert r.status_code == 422 and r.json()["detail"]["rechazados"][0]["referencia_externa"] == "a"


def test_origen_manual_no_entra_por_la_api_interna(client, interna):
    r = client.post("/internal/tesoreria/lotes", headers=interna,
                    json={"origen": "MANUAL", "referencia_origen": "x", "pagos": [pago("a")]})
    assert r.status_code == 422


def test_carga_manual(client, teso):
    r = client.post("/api/tesoreria/lotes", headers=teso, json={"descripcion": "Proveedores septiembre", "pagos": [
        {"beneficiario": "Imprenta SA", "documento": "30-71234567-8", "cbu": "0110599520000001234567", "monto": 150000.5},
        {"beneficiario": "Limpieza SRL", "cbu": "0110599520000007654321", "monto": 80000}]})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["origen"] == "MANUAL" and d["creado_por"] == "teso" and d["total"] == 230000.5
    refs = [p["referencia_externa"] for p in d["pagos"]]
    assert refs[0].startswith("manual-") and refs[0].endswith("-1") and refs[1].endswith("-2")
    assert d["pagos"][0]["documento"] == "30712345678"


def test_dos_lotes_manuales_seguidos_no_se_pisan(client, teso):
    """Regresión: con "manual-1" fijo, el segundo lote descartaba sus pagos por "ya está en otro lote"."""
    cuerpo = {"descripcion": "Proveedores", "pagos": [{"beneficiario": "Imprenta SA", "cbu": "0110599520000001234567", "monto": 10}]}
    a = client.post("/api/tesoreria/lotes", headers=teso, json=cuerpo)
    b = client.post("/api/tesoreria/lotes", headers=teso, json=cuerpo)
    assert a.status_code == b.status_code == 201, b.text
    assert b.json()["cantidad"] == 1 and b.json()["rechazados"] == []


def test_carga_manual_exige_permiso(client):
    r = client.post("/api/tesoreria/lotes", headers=gateway("lotes:read"),
                    json={"descripcion": "x", "pagos": [{"beneficiario": "a", "cbu": "1" * 22, "monto": 1}]})
    assert r.status_code == 403


def test_listado_con_filtros_y_sin_identidad(client, lote_creditos, teso):
    lote_creditos()
    client.post("/api/tesoreria/lotes", headers=teso, json={"descripcion": "m", "pagos": [
        {"beneficiario": "a", "cbu": "1" * 22, "monto": 1}]})
    assert len(client.get("/api/tesoreria/lotes?origen=MANUAL", headers=teso).json()["items"]) == 1
    d = client.get("/api/tesoreria/lotes?estado=PENDIENTE_APROBACION", headers=teso).json()
    assert len(d["items"]) == 2 and d["pendientes"] == 2 and d["envio_simulado"] is True
    assert client.get("/api/tesoreria/lotes").status_code == 401
    assert client.get("/api/tesoreria/lotes/999", headers=teso).status_code == 404
