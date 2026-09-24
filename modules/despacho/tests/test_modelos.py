"""Catálogo de modelos (plantillas) de resoluciones y disposiciones."""


def test_el_codigo_se_autoasigna(client, h, modelo):
    a = modelo(descripcion="TRANSFERENCIA")
    b = modelo(descripcion="BAJA")
    assert b["codigo"] == a["codigo"] + 1


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
