"""Documentación del cliente: carga manual, copia desde otro módulo (API interna), vista y baja."""
import base64
from urllib.parse import quote

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 300
PDF = b"%PDF-1.4\n" + b"1" * 300
CAPTURA = "Captura de pantalla 2026-09-22 a la(s) 11.46.03 a. m.png"


def _subir(client, h, cid, contenido=PNG, nombre="dni.png", tipo="DNI_FRENTE", ct="image/png"):
    return client.post(f"/api/clientes/{cid}/documentos", headers=h,
                       files={"archivo": (nombre, contenido, ct)}, data={"tipo": tipo})


def test_carga_lista_y_descarga(client, h, crear_ph):
    cid = crear_ph()["id"]
    r = _subir(client, h, cid)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["tipo"] == "DNI_FRENTE" and doc["tamano"] == len(PNG) and doc["origen"] == "Carga manual"

    d = client.get(f"/api/clientes/{cid}/documentos", headers=h).json()
    assert [x["id"] for x in d["items"]] == [doc["id"]] and d["tipos"]["RECIBO"] == "Recibo de sueldo"
    assert "contenido" not in d["items"][0]          # el listado no trae los bytes

    dl = client.get(f"/api/clientes/{cid}/documentos/{doc['id']}", headers=h)
    assert dl.status_code == 200 and dl.content == PNG and dl.headers["content-type"] == "image/png"


def test_nombre_con_caracteres_especiales_se_descarga(client, h, crear_ph):
    """Regresión del 500 de Créditos: el espacio angosto de las capturas de macOS en el encabezado."""
    cid = crear_ph()["id"]
    doc = _subir(client, h, cid, nombre=CAPTURA).json()
    dl = client.get(f"/api/clientes/{cid}/documentos/{doc['id']}", headers=h)
    assert dl.status_code == 200
    assert f"filename*=UTF-8''{quote(CAPTURA, safe='')}" in dl.headers["content-disposition"]


def test_valida_formato_tamano_y_duplicados(client, h, crear_ph):
    cid = crear_ph()["id"]
    assert _subir(client, h, cid, contenido=b"hola", nombre="x.txt", ct="text/plain").status_code == 422
    assert _subir(client, h, cid, contenido=b"\x89PNG" + b"0" * (10 * 1024 * 1024), nombre="grande.png").status_code == 422
    assert _subir(client, h, cid).status_code == 201
    r = _subir(client, h, cid, nombre="otra-copia.png")          # mismo contenido → no se duplica
    assert r.status_code == 409 and "dni.png" in r.json()["detail"]
    assert _subir(client, h, cid, contenido=PDF, nombre="recibo.pdf", tipo="RECIBO", ct="application/pdf").status_code == 201


def test_cliente_o_documento_inexistente(client, h, crear_ph):
    cid = crear_ph()["id"]
    assert client.get("/api/clientes/9999/documentos", headers=h).status_code == 404
    assert _subir(client, h, 9999).status_code == 404
    assert client.get(f"/api/clientes/{cid}/documentos/123", headers=h).status_code == 404


def test_un_documento_no_se_ve_desde_otro_cliente(client, h, crear_ph):
    a = crear_ph(documento="20111111")["id"]
    b = crear_ph(nombre="Ana", documento="20222222", email="ana@x.com")["id"]
    doc = _subir(client, h, a).json()
    assert client.get(f"/api/clientes/{b}/documentos/{doc['id']}", headers=h).status_code == 404
    assert client.delete(f"/api/clientes/{b}/documentos/{doc['id']}", headers=h).status_code == 404


def test_baja(client, h, crear_ph):
    cid = crear_ph()["id"]
    doc = _subir(client, h, cid).json()
    assert client.delete(f"/api/clientes/{cid}/documentos/{doc['id']}", headers=h).status_code == 204
    assert client.get(f"/api/clientes/{cid}/documentos", headers=h).json()["items"] == []


def test_sin_identidad_del_gateway_es_rechazado(client, crear_ph, h):
    cid = crear_ph()["id"]
    assert client.get(f"/api/clientes/{cid}/documentos").status_code == 422   # falta X-User-Id


def test_copia_desde_otro_modulo_es_idempotente(client, h, crear_ph):
    """Créditos manda los adjuntos de la solicitud; repetir la copia no duplica."""
    cid = crear_ph()["id"]
    lote = {"documentos": [
        {"nombre": CAPTURA, "content_type": "image/png", "tipo": "DNI_FRENTE",
         "origen": "Solicitud SOL-2026-00001", "contenido_base64": base64.b64encode(PNG).decode()},
        {"nombre": "recibo.pdf", "content_type": "application/pdf", "tipo": "RECIBO",
         "origen": "Solicitud SOL-2026-00001", "contenido_base64": base64.b64encode(PDF).decode()},
    ]}
    r = client.post(f"/internal/clientes/{cid}/documentos", json=lote)
    assert r.status_code == 200 and r.json()["guardados"] == 2 and r.json()["repetidos"] == 0
    r = client.post(f"/internal/clientes/{cid}/documentos", json=lote)
    assert r.json()["guardados"] == 0 and r.json()["repetidos"] == 2
    items = client.get(f"/api/clientes/{cid}/documentos", headers=h).json()["items"]
    assert len(items) == 2 and {i["origen"] for i in items} == {"Solicitud SOL-2026-00001"}


def test_copia_con_contenido_invalido_o_cliente_inexistente(client, crear_ph):
    cid = crear_ph()["id"]
    malo = {"documentos": [{"nombre": "x.png", "content_type": "image/png", "contenido_base64": "no-es-base64!!"}]}
    assert client.post(f"/internal/clientes/{cid}/documentos", json=malo).status_code == 422
    assert client.post("/internal/clientes/9999/documentos", json={"documentos": []}).status_code == 404
