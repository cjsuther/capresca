"""Envío por Interbanking: simulación, modo real, fallidos, inciertos y avisos al origen."""
from tests.conftest import gateway, pago
from app.services import interbanking


def _aprobado(client, lote_creditos, teso):
    lid = lote_creditos()["id"]
    client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso)
    return lid


def test_enviar_exige_permiso_y_lote_aprobado(client, lote_creditos, teso):
    lid = lote_creditos()["id"]
    assert client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).status_code == 409   # sin aprobar
    client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso)
    r = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=gateway("lotes:read", "aprobaciones:aprobar"))
    assert r.status_code == 403 and "lotes:enviar" in r.json()["detail"]


def test_en_simulacion_no_se_llama_al_banco(client, lote_creditos, teso, origen, monkeypatch):
    monkeypatch.setattr(interbanking, "enviar", lambda *a: (_ for _ in ()).throw(AssertionError("no debía llamar al banco")))
    lid = _aprobado(client, lote_creditos, teso)
    d = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).json()
    assert d["estado"] == "ENVIADO" and d["simulado"] is True
    assert {p["estado_banco"] for p in d["pagos"]} == {"SIMULADO"} and d["pagos"][0]["id_operacion_ib"].startswith("SIM-")
    d = client.post(f"/api/tesoreria/lotes/{lid}/actualizar", headers=teso).json()
    assert d["estado"] == "CONFIRMADO" and d["cambios"] == 2
    avisados = {p["referencia_externa"]: p["estado"] for p in origen.recibidos[-1][2]["pagos"]}
    assert avisados == {"cto-1": "CONFIRMADO", "cto-2": "CONFIRMADO"} and origen.recibidos[-1][2]["simulado"]


def test_no_se_envia_dos_veces(client, lote_creditos, teso):
    lid = _aprobado(client, lote_creditos, teso)
    assert client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).status_code == 200
    assert client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).status_code == 409


def test_modo_real_envia_y_confirma(client, lote_creditos, teso, banco, origen):
    lid = _aprobado(client, lote_creditos, teso)
    d = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).json()
    assert d["simulado"] is False and len(banco.enviados) == 2
    cbu, monto, concepto = banco.enviados[0]
    assert cbu == "2850590940090418135201" and monto == 500000.0 and concepto.startswith(d["codigo"])
    assert [p["estado"] for p in d["pagos"]] == ["ENVIADO", "ENVIADO"]
    banco.estados = {1: "ACREDITADA"}
    d = client.post(f"/api/tesoreria/lotes/{lid}/actualizar", headers=teso).json()
    assert [p["estado"] for p in d["pagos"]] == ["CONFIRMADO", "ENVIADO"] and d["estado"] == "ENVIADO"
    banco.estados[2] = "RECHAZADA"
    d = client.post(f"/api/tesoreria/lotes/{lid}/actualizar", headers=teso).json()
    assert d["pagos"][1]["estado"] == "FALLIDO" and d["estado"] == "CON_ERRORES"
    ultimos = {p["referencia_externa"]: p["estado"] for _u, _h, c in origen.recibidos for p in c["pagos"]}
    assert ultimos == {"cto-1": "CONFIRMADO", "cto-2": "FALLIDO"}


def test_fallido_se_reintenta(client, lote_creditos, teso, banco):
    banco.respuestas = [{"status": "ACREDITADA"}, interbanking.EnvioRechazado("CBU inexistente")]
    lid = _aprobado(client, lote_creditos, teso)
    d = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).json()
    assert [p["estado"] for p in d["pagos"]] == ["CONFIRMADO", "FALLIDO"] and d["estado"] == "CON_ERRORES"
    assert "CBU inexistente" in d["pagos"][1]["motivo"]
    d = client.post(f"/api/tesoreria/lotes/{lid}/pagos/{d['pagos'][1]['id']}/reintentar", headers=teso).json()
    assert d["pagos"][1]["estado"] == "ENVIADO" and d["estado"] == "ENVIADO" and len(banco.enviados) == 3


def test_fallido_que_el_origen_ya_reenvio_no_se_reintenta(client, lote_creditos, teso, banco):
    """Un pago vivo por referencia: si Créditos ya lo mandó en otro lote, reintentarlo lo pagaría dos veces."""
    banco.respuestas = [{"status": "ACREDITADA"}, interbanking.EnvioRechazado("CBU inexistente")]
    lid = _aprobado(client, lote_creditos, teso)
    d = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).json()
    nuevo = lote_creditos("reintento cto-2", pagos=[pago("cto-2", 300000)])
    r = client.post(f"/api/tesoreria/lotes/{lid}/pagos/{d['pagos'][1]['id']}/reintentar", headers=teso)
    assert r.status_code == 409 and nuevo["codigo"] in r.json()["detail"]
    assert len(banco.enviados) == 2


def test_incierto_no_se_reintenta_y_se_resuelve_a_mano(client, lote_creditos, teso, banco):
    banco.respuestas = [interbanking.EnvioIncierto("timeout"), {"status": "ACREDITADA"}]
    lid = _aprobado(client, lote_creditos, teso)
    d = client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso).json()
    pid = d["pagos"][0]["id"]
    assert d["pagos"][0]["estado"] == "INCIERTO" and "no se reintenta" in d["pagos"][0]["motivo"]
    assert client.post(f"/api/tesoreria/lotes/{lid}/pagos/{pid}/reintentar", headers=teso).status_code == 409
    assert client.post(f"/api/tesoreria/lotes/{lid}/pagos/{pid}/resolver", headers=teso,
                       json={"resultado": "CONFIRMADO"}).status_code == 422          # sin observación
    d = client.post(f"/api/tesoreria/lotes/{lid}/pagos/{pid}/resolver", headers=teso,
                    json={"resultado": "CONFIRMADO", "observacion": "Figura acreditada en el extracto del 22/9"}).json()
    assert d["pagos"][0]["estado"] == "CONFIRMADO" and d["estado"] == "CONFIRMADO"
    assert len(banco.enviados) == 2                                          # nunca se reenvió


def test_si_el_origen_no_responde_el_aviso_se_reintenta(client, lote_creditos, teso, origen):
    lid = _aprobado(client, lote_creditos, teso)
    client.post(f"/api/tesoreria/lotes/{lid}/enviar", headers=teso)
    origen.caido = True
    client.post(f"/api/tesoreria/lotes/{lid}/actualizar", headers=teso)
    assert origen.recibidos == []
    origen.caido = False
    client.post(f"/api/tesoreria/lotes/{lid}/actualizar", headers=teso)
    assert {p["estado"] for p in origen.recibidos[0][2]["pagos"]} == {"CONFIRMADO"}
    client.post(f"/api/tesoreria/lotes/{lid}/actualizar", headers=teso)
    assert len(origen.recibidos) == 1                                        # no se avisa dos veces


def test_clasificacion_de_estados_del_banco():
    assert interbanking.clasificar("acreditada") == "CONFIRMADO"
    assert interbanking.clasificar("RECHAZADA") == "FALLIDO"
    assert interbanking.clasificar("INICIADA") == "ENVIADO"
    assert interbanking.clasificar("") == "ENVIADO"
