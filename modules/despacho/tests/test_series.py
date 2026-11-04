"""Catálogo de series de numeración: se administran desde Catálogos en lugar de estar en el código."""
from tests.conftest import gateway

URL = "/api/despacho/series"


def _series(client, h, **params):
    return client.get(URL, headers=h, params=params).json()


def test_trae_las_series_iniciales_en_su_orden(client, h):
    assert [(s["serie"], s["nombre"]) for s in _series(client, h)] == [
        (1, "GENERAL"), (3, "CRÉDITOS"), (6, "JUEGOS"), (4, "SEGUROS"), (5, "PROVEEDORES Y OBRAS")]


def test_se_crea_una_serie_y_se_puede_usar(client, h):
    r = client.post(URL, headers=h, json={"serie": 8, "nombre": "  recursos   humanos "})
    assert r.status_code == 201, r.text
    assert r.json() == {"serie": 8, "nombre": "RECURSOS HUMANOS", "orden": 6, "activa": True, "en_uso": False}
    assert _series(client, h)[-1]["serie"] == 8

    m = client.post("/api/despacho/modelos", headers=h,
                    json={"descripcion": "LICENCIA", "codigo": 900, "serie": 8})
    assert m.status_code == 201 and m.json()["serie_nombre"] == "RECURSOS HUMANOS"
    res = client.post("/api/despacho/resoluciones", headers=h, json={"tipo": "RES", "serie": 8, "asunto": "x"})
    assert res.status_code == 201 and res.json()["numero"] == 1 and res.json()["serie_nombre"] == "RECURSOS HUMANOS"
    # Aparece en la numeración del año con su propio correlativo.
    num = client.get("/api/despacho/numeracion", headers=h, params={"anio": res.json()["anio"]}).json()
    assert any(x["serie"] == 8 and x["proximoNumero"] == 2 for x in num)


def test_no_se_repite_ni_el_numero_ni_el_nombre(client, h):
    assert client.post(URL, headers=h, json={"serie": 6, "nombre": "OTRA"}).status_code == 409
    r = client.post(URL, headers=h, json={"serie": 9, "nombre": "juegos"})
    assert r.status_code == 409 and "6" in r.json()["detail"]
    assert client.post(URL, headers=h, json={"serie": 0, "nombre": "CERO"}).status_code == 422
    assert client.post(URL, headers=h, json={"serie": 9, "nombre": "   "}).status_code == 422


def test_se_renombra_y_reordena_sin_cambiar_el_numero(client, h, resolucion):
    r = resolucion(serie=4)
    e = client.put(f"{URL}/4", headers=h, json={"nombre": "SEGUROS Y RIESGOS", "orden": 0})
    assert e.status_code == 200 and e.json()["serie"] == 4
    assert _series(client, h)[0]["nombre"] == "SEGUROS Y RIESGOS"
    # Lo ya emitido muestra el nombre nuevo: la serie es la misma.
    assert client.get(f"/api/despacho/resoluciones/{r['id']}", headers=h).json()["serie_nombre"] == "SEGUROS Y RIESGOS"
    assert client.put(f"{URL}/4", headers=h, json={"nombre": "GENERAL"}).status_code == 409
    assert client.put(f"{URL}/99", headers=h, json={"nombre": "X"}).status_code == 404


def test_una_serie_inactiva_no_se_ofrece_para_lo_nuevo(client, h, modelo):
    m = client.post("/api/despacho/modelos", headers=h,
                    json={"descripcion": "SINIESTRO", "codigo": 500, "serie": 4}).json()
    r = client.post(f"{URL}/4/activa", headers=h, json={"activa": False})
    assert r.status_code == 200 and r.json()["activa"] is False

    assert all(s["serie"] != 4 for s in _series(client, h))
    assert any(s["serie"] == 4 for s in _series(client, h, incluir_inactivas=True))
    nuevo = client.post("/api/despacho/modelos", headers=h, json={"descripcion": "OTRO", "codigo": 501, "serie": 4})
    assert nuevo.status_code == 422 and "inactiva" in nuevo.json()["detail"]
    acto = client.post("/api/despacho/resoluciones", headers=h, json={"tipo": "RES", "serie": 4})
    assert acto.status_code == 422

    # El modelo que ya era de esa serie se sigue pudiendo editar.
    e = client.put(f"/api/despacho/modelos/{m['id']}", headers=h,
                   json={"descripcion": "SINIESTRO GRAVE", "tipo": "RES", "serie": 4})
    assert e.status_code == 200, e.text

    assert client.post(f"{URL}/4/activa", headers=h, json={"activa": True}).json()["activa"] is True


def test_la_serie_por_defecto_no_se_desactiva_ni_se_borra(client, h):
    assert client.post(f"{URL}/1/activa", headers=h, json={"activa": False}).status_code == 422
    assert client.delete(f"{URL}/1", headers=h).status_code == 422


def test_se_borra_solo_si_no_tiene_uso(client, h, resolucion):
    client.post(URL, headers=h, json={"serie": 8, "nombre": "POR ERROR"})
    assert client.delete(f"{URL}/8", headers=h).status_code == 204
    assert all(s["serie"] != 8 for s in _series(client, h, incluir_inactivas=True))

    resolucion(serie=6)
    assert next(s for s in _series(client, h) if s["serie"] == 6)["en_uso"] is True
    r = client.delete(f"{URL}/6", headers=h)
    assert r.status_code == 409 and "desactivala" in r.json()["detail"]


def test_una_serie_fuera_del_catalogo_se_muestra_por_su_numero(client, h, db, resolucion):
    """Un acto importado puede traer un TIPO_RES que no está en el catálogo: no se pierde."""
    from app.models import Resolucion
    r = resolucion()
    db.get(Resolucion, r["id"]).serie = 77
    db.commit()
    db.expire_all()
    assert client.get(f"/api/despacho/resoluciones/{r['id']}", headers=h).json()["serie_nombre"] == "Serie 77"


def test_administrar_series_pide_su_permiso(client, solo_lectura):
    assert client.get(URL, headers=solo_lectura).status_code == 200
    sin = gateway("resoluciones:read", "modelos:write")
    assert client.post(URL, headers=sin, json={"serie": 8, "nombre": "X"}).status_code == 403
    assert client.put(f"{URL}/4", headers=sin, json={"nombre": "X"}).status_code == 403
    assert client.post(f"{URL}/4/activa", headers=sin, json={"activa": False}).status_code == 403
    assert client.delete(f"{URL}/4", headers=sin).status_code == 403
