"""Revisión (exclusiones) y aprobación según el workflow de Configuraciones."""
from tests.conftest import gateway


def _lote(client, lote_creditos, teso):
    r = lote_creditos()
    return r["id"], client.get(f"/api/tesoreria/lotes/{r['id']}", headers=teso).json()


def test_con_la_regla_inactiva_aprueba_quien_tiene_el_permiso(client, lote_creditos, teso):
    lid, d = _lote(client, lote_creditos, teso)
    assert d["puede_aprobar"] and d["niveles"] == 1
    sin_permiso = gateway("lotes:read")
    r = client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=sin_permiso)
    assert r.status_code == 403 and "aprobaciones:aprobar" in r.json()["detail"]
    r = client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso)
    assert r.status_code == 200 and r.json()["estado"] == "APROBADO"
    assert r.json()["aprobaciones"][0]["aprobado_por"] == "teso"


def test_excluir_un_pago_y_volverlo_a_incluir(client, lote_creditos, teso, origen):
    lid, d = _lote(client, lote_creditos, teso)
    pid = d["pagos"][1]["id"]
    assert client.post(f"/api/tesoreria/lotes/{lid}/pagos/{pid}/excluir", headers=teso, json={"motivo": ""}).status_code == 422
    r = client.post(f"/api/tesoreria/lotes/{lid}/pagos/{pid}/excluir", headers=teso, json={"motivo": "CBU observado"})
    assert r.json()["pagos"][1]["estado"] == "EXCLUIDO" and r.json()["cantidad"] == 1 and r.json()["total"] == 500000.0
    # el último pago no se excluye: para no enviar nada se rechaza el lote
    otro = d["pagos"][0]["id"]
    assert client.post(f"/api/tesoreria/lotes/{lid}/pagos/{otro}/excluir", headers=teso, json={"motivo": "x"}).status_code == 409
    r = client.post(f"/api/tesoreria/lotes/{lid}/pagos/{pid}/incluir", headers=teso)
    assert r.json()["pagos"][1]["estado"] == "PENDIENTE"
    assert origen.recibidos == []                 # la exclusión se avisa recién al aprobar


def test_al_aprobar_se_avisan_los_excluidos_al_origen(client, lote_creditos, teso, origen):
    lid, d = _lote(client, lote_creditos, teso)
    client.post(f"/api/tesoreria/lotes/{lid}/pagos/{d['pagos'][1]['id']}/excluir", headers=teso, json={"motivo": "Sin CBU propio"})
    client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso)
    url, headers, cuerpo = origen.recibidos[0]
    assert url.endswith("/internal/creditos/tesoreria/resultado") and headers == {"X-Api-Key": "clave-de-test"}
    assert cuerpo["pagos"] == [{"referencia_externa": "cto-2", "estado": "EXCLUIDO", "motivo": "Sin CBU propio",
                                "id_operacion_ib": "", "monto": 300000.0}]


def test_workflow_de_dos_niveles_con_cuatro_ojos(client, lote_creditos, wf):
    wf.activar([{"orden": 1, "nombre": "Tesorero", "rol": "APROBAR", "cuatroOjos": True, "usuarios": []},
                {"orden": 2, "nombre": "Gerencia", "rol": "SUPERVISAR", "cuatroOjos": True, "usuarios": []}])
    lid = lote_creditos()["id"]
    tesorero = gateway("lotes:read", "aprobaciones:aprobar", username="teso")
    gerente = gateway("lotes:read", "aprobaciones:supervisar", "aprobaciones:aprobar", username="gerente", user_id=9)
    # quien armó el lote en Créditos no aprueba (cuatro-ojos)
    creador = gateway("aprobaciones:aprobar", username="ana.creditos", user_id=3)
    assert client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=creador).status_code == 409
    r = client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=tesorero)
    assert r.json()["estado"] == "PENDIENTE_APROBACION" and r.json()["nivel_actual"] == 2
    # el tesorero no puede cerrar el nivel 2 (rol SUPERVISAR)
    assert client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=tesorero).status_code == 403
    r = client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=gerente)
    assert r.json()["estado"] == "APROBADO" and [a["aprobado_por"] for a in r.json()["aprobaciones"]] == ["teso", "gerente"]


def test_quien_aprobo_un_nivel_no_aprueba_el_siguiente(client, lote_creditos, wf):
    wf.activar([{"orden": 1, "nombre": "N1", "rol": "APROBAR", "cuatroOjos": True, "usuarios": []},
                {"orden": 2, "nombre": "N2", "rol": "APROBAR", "cuatroOjos": True, "usuarios": []}])
    lid = lote_creditos()["id"]
    h = gateway("aprobaciones:aprobar", username="teso")
    client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=h)
    r = client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=h)
    assert r.status_code == 409 and "Cuatro-ojos" in r.json()["detail"]


def test_excepciones_por_usuario(client, lote_creditos, wf):
    wf.activar([{"orden": 1, "nombre": "Tesorero", "rol": "APROBAR", "cuatroOjos": True, "usuarios": [
        {"username": "teso", "modo": "EXCLUIR"}, {"username": "contador", "modo": "INCLUIR"}]}])
    lid = lote_creditos()["id"]
    assert client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=gateway("aprobaciones:aprobar", username="teso")).status_code == 403
    r = client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=gateway("lotes:read", username="contador"))
    assert r.json()["estado"] == "APROBADO"


def test_excluir_un_pago_reinicia_la_aprobacion(client, lote_creditos, wf, teso):
    wf.activar([{"orden": 1, "nombre": "N1", "rol": "APROBAR", "cuatroOjos": True, "usuarios": []},
                {"orden": 2, "nombre": "N2", "rol": "APROBAR", "cuatroOjos": True, "usuarios": []}])
    lid = lote_creditos()["id"]
    d = client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso).json()
    assert len(d["aprobaciones"]) == 1
    d = client.post(f"/api/tesoreria/lotes/{lid}/pagos/{d['pagos'][0]['id']}/excluir", headers=teso, json={"motivo": "x"}).json()
    assert d["aprobaciones"] == [] and "APROBACIONES_REINICIADAS" in [e["accion"] for e in d["eventos"]]


def test_sin_configuraciones_no_se_aprueba(client, lote_creditos, wf, teso):
    lid = lote_creditos()["id"]
    wf.caido = True
    from app.services import workflow
    workflow._cache.clear()
    assert client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso).status_code == 503


def test_rechazar_el_lote(client, lote_creditos, teso, origen):
    lid = lote_creditos()["id"]
    assert client.post(f"/api/tesoreria/lotes/{lid}/rechazar", headers=teso, json={"motivo": ""}).status_code == 422
    r = client.post(f"/api/tesoreria/lotes/{lid}/rechazar", headers=teso, json={"motivo": "Montos a revisar"})
    assert r.json()["estado"] == "RECHAZADO" and {p["estado"] for p in r.json()["pagos"]} == {"RECHAZADO"}
    assert {p["estado"] for p in origen.recibidos[0][2]["pagos"]} == {"RECHAZADO"}
    assert client.post(f"/api/tesoreria/lotes/{lid}/aprobar", headers=teso).status_code == 409
