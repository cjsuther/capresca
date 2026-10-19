"""Catálogo de modelos (plantillas) de resoluciones y disposiciones."""


def test_el_codigo_lo_carga_el_usuario(client, h, modelo):
    assert modelo(descripcion="TRANSFERENCIA", codigo=42)["codigo"] == 42


def test_el_codigo_es_obligatorio_y_numerico(client, h):
    r = client.post("/api/despacho/modelos", headers=h, json={"descripcion": "BAJA", "tipo": "RES"})
    assert r.status_code == 422 and "código" in r.json()["detail"]
    r = client.post("/api/despacho/modelos", headers=h, json={"descripcion": "BAJA", "codigo": 0})
    assert r.status_code == 422
    r = client.post("/api/despacho/modelos", headers=h, json={"descripcion": "BAJA", "codigo": "abc"})
    assert r.status_code == 422


def test_el_codigo_no_se_repite_ni_entre_series(client, h, modelo):
    modelo(descripcion="TRANSFERENCIA", codigo=42)
    r = client.post("/api/despacho/modelos", headers=h,
                    json={"descripcion": "BAJA", "codigo": 42, "serie": 6})
    assert r.status_code == 409 and "TRANSFERENCIA" in r.json()["detail"]


def test_el_codigo_se_puede_cambiar(client, h, modelo):
    a = modelo(descripcion="TRANSFERENCIA", codigo=42)
    b = modelo(descripcion="BAJA", codigo=43)
    datos = {"descripcion": "TRANSFERENCIA", "tipo": "RES"}
    r = client.put(f"/api/despacho/modelos/{a['id']}", headers=h, json={**datos, "codigo": 50})
    assert r.status_code == 200 and r.json()["codigo"] == 50
    # Guardar sin cambiarlo (o con el propio) no choca consigo mismo.
    assert client.put(f"/api/despacho/modelos/{a['id']}", headers=h, json={**datos, "codigo": 50}).status_code == 200
    r = client.put(f"/api/despacho/modelos/{a['id']}", headers=h, json={**datos, "codigo": b["codigo"]})
    assert r.status_code == 409 and "BAJA" in r.json()["detail"]


def test_la_descripcion_es_obligatoria(client, h):
    r = client.post("/api/despacho/modelos", headers=h, json={"descripcion": "   ", "tipo": "RES"})
    assert r.status_code == 422 and "descripción" in r.json()["detail"]


def test_tiene_plantilla_refleja_si_hay_cuerpo(client, h, modelo):
    con = modelo(descripcion="CON", plantilla="<p>algo</p>")
    sin = modelo(descripcion="SIN", plantilla="")
    assert con["tiene_plantilla"] is True and sin["tiene_plantilla"] is False


def test_se_edita_y_se_puede_desactivar(client, h, modelo):
    m = modelo(descripcion="VIEJO")
    e = client.put(f"/api/despacho/modelos/{m['id']}", headers=h,
                   json={"descripcion": "NUEVO", "tipo": "DIS", "plantilla": "<p>x</p>",
                         "activo": False})
    assert e.status_code == 200
    assert (e.json()["descripcion"], e.json()["tipo"], e.json()["activo"]) == ("NUEVO", "DIS", False)

    # Por defecto el listado muestra sólo los activos.
    assert all(x["id"] != m["id"] for x in client.get("/api/despacho/modelos", headers=h).json())
    con_inactivos = client.get("/api/despacho/modelos?incluir_inactivos=true", headers=h).json()
    assert any(x["id"] == m["id"] for x in con_inactivos)


def test_el_listado_filtra_por_tipo_y_texto(client, h, modelo):
    modelo(descripcion="TRANSFERENCIA DE FONDOS", tipo="RES")
    modelo(descripcion="BAJA DE AFILIADO", tipo="DIS")
    assert len(client.get("/api/despacho/modelos?tipo=DIS", headers=h).json()) == 1
    assert len(client.get("/api/despacho/modelos?buscar=transfer", headers=h).json()) == 1


def test_editar_modelos_pide_su_permiso(client, solo_lectura, h, modelo):
    m = modelo()
    r = client.put(f"/api/despacho/modelos/{m['id']}", headers=solo_lectura,
                   json={"descripcion": "x", "tipo": "RES"})
    assert r.status_code == 403 and "modelos:write" in r.json()["detail"]


# --------------------------------------------------------------------------- sector, actividad, baja
def test_el_modelo_lleva_sector_y_actividad(client, h):
    r = client.post("/api/despacho/modelos", headers=h,
                    json={"descripcion": "OTORGAMIENTO", "tipo": "RES", "codigo": 77, "sector": "Créditos",
                          "actividad": "Préstamos personales"})
    assert r.status_code == 201
    assert (r.json()["sector"], r.json()["actividad"]) == ("Créditos", "Préstamos personales")
    e = client.put(f"/api/despacho/modelos/{r.json()['id']}", headers=h,
                   json={"descripcion": "OTORGAMIENTO", "tipo": "RES", "sector": "Seguros"})
    assert (e.json()["sector"], e.json()["actividad"]) == ("Seguros", "Préstamos personales")
    assert len(client.get("/api/despacho/modelos?sector=Seguros", headers=h).json()) == 1
    assert client.get("/api/despacho/modelos?sector=Créditos", headers=h).json() == []


def test_el_modelo_se_inactiva_y_se_reactiva(client, h, modelo):
    m = modelo()
    r = client.post(f"/api/despacho/modelos/{m['id']}/activo", headers=h, json={"activo": False})
    assert r.status_code == 200 and r.json()["activo"] is False
    # Inactivo no se usa para redactar.
    no = client.post("/api/despacho/resoluciones", headers=h, json={"tipo": "RES", "modelo_id": m["id"]})
    assert no.status_code == 422 and "inactivo" in no.json()["detail"]
    assert client.post(f"/api/despacho/modelos/{m['id']}/activo", headers=h,
                       json={"activo": True}).json()["activo"] is True


def test_eliminar_un_modelo_no_toca_los_actos_que_lo_usaron(client, h, modelo, resolucion):
    m = modelo(descripcion="TRANSFERENCIA")
    r = resolucion(modelo_id=m["id"])
    assert client.delete(f"/api/despacho/modelos/{m['id']}", headers=h).status_code == 204
    assert client.get(f"/api/despacho/modelos/{m['id']}", headers=h).status_code == 404
    d = client.get(f"/api/despacho/resoluciones/{r['id']}", headers=h).json()
    assert d["modelo_id"] is None and d["motivo"] == "TRANSFERENCIA"


def test_eliminar_y_desactivar_modelos_pide_su_permiso(client, solo_lectura, modelo):
    m = modelo()
    assert client.delete(f"/api/despacho/modelos/{m['id']}", headers=solo_lectura).status_code == 403
    assert client.post(f"/api/despacho/modelos/{m['id']}/activo", headers=solo_lectura,
                       json={"activo": False}).status_code == 403
