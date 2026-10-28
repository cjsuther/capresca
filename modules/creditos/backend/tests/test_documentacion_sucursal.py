"""Solicitudes cargadas en la plataforma (sucursal): piden la misma documentación y datos que el portal, y no
entran a evaluación sin la documentación obligatoria de su línea."""
import pytest
from fastapi.testclient import TestClient

from tests.documentacion import PNG, adjuntar_pedidos
from tests.test_portal import SALUD, TODOS_LOS_DOCS, _configurar_requisitos, _enviar, _ingresar, _un_producto

URL = "/api/creditos/solicitudes"


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _pers_id(client, h):
    return next(p for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"]
                if p["codigo"] == "LP-PERS-01")["id"]


def _crear(client, h, **kw):
    d = {"producto_id": _pers_id(client, h), "monto_solicitado": 1_000_000, "plazo_solicitado": 24,
         "solicitante_tipo": "REGISTRADO",
         "cliente_id": client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]}
    d.update(kw)
    r = client.post(URL, headers=h, json=d)
    assert r.status_code == 201, r.text
    return r.json()


def _adjuntar(client, h, sid, tipo, contenido=PNG, ct="image/png", nombre=None):
    return client.post(f"{URL}/{sid}/documentos", headers=h, data={"tipo": tipo},
                       files={"archivo": (nombre or f"{tipo.lower()}.png", contenido, ct)})


def _enviar_a_evaluacion(client, h, sid):
    return client.post(f"{URL}/{sid}/estado", headers=h, json={"accion": "enviar"})


def _parametro(client, h, valor):
    r = client.post("/api/creditos/admin/parametros", headers=h,
                    json={"clave": "PORTAL_DOCUMENTOS", "valor": valor, "ambito": "creditos"})
    assert r.status_code in (200, 201), r.text


def test_la_linea_pide_lo_mismo_que_en_el_portal(client):
    h, hp = _auth(client), _ingresar(client)
    pid = _pers_id(client, h)
    bo = client.get(f"{URL}/requisitos/{pid}", headers=h).json()
    portal = client.get(f"/api/creditos/portal/productos/{pid}/requisitos", headers=hp).json()
    assert bo == portal
    assert {d["tipo"] for d in bo["documentos"]} == TODOS_LOS_DOCS


def test_sin_la_documentacion_obligatoria_no_se_envia_a_evaluacion(client):
    h = _auth(client)
    s = _crear(client, h)
    r = _enviar_a_evaluacion(client, h, s["id"])
    assert r.status_code == 409 and "Falta documentación obligatoria" in r.text and "Recibo de sueldo" in r.text
    docs = client.get(f"{URL}/{s['id']}/documentos", headers=h).json()
    assert docs["puedeAdjuntar"] is True and len(docs["faltantes"]) == len(TODOS_LOS_DOCS)

    adjuntar_pedidos(client, h, s["id"])
    docs = client.get(f"{URL}/{s['id']}/documentos", headers=h).json()
    assert docs["faltantes"] == [] and len(docs["items"]) == len(TODOS_LOS_DOCS)
    assert {d["subido_por"] for d in docs["items"]} == {"admin"}
    r = _enviar_a_evaluacion(client, h, s["id"])
    assert r.status_code == 200 and r.json()["estado"] == "EN_EVALUACION"


def test_respeta_la_documentacion_configurada_en_parametros(client):
    h = _auth(client)
    _parametro(client, h, "DNI_FRENTE,RECIBO")
    s = _crear(client, h)
    assert _adjuntar(client, h, s["id"], "SELFIE_DNI").status_code == 422     # no se pide
    assert _adjuntar(client, h, s["id"], "DNI_FRENTE").status_code == 201
    r = _enviar_a_evaluacion(client, h, s["id"])
    assert r.status_code == 409 and "Recibo de sueldo" in r.text and "DNI" not in r.json()["detail"].split(":")[1]
    assert _adjuntar(client, h, s["id"], "RECIBO").status_code == 201
    assert _enviar_a_evaluacion(client, h, s["id"]).json()["estado"] == "EN_EVALUACION"


def test_parametro_vacio_no_pide_documentacion(client):
    h = _auth(client)
    _parametro(client, h, "")
    s = _crear(client, h)
    assert _enviar_a_evaluacion(client, h, s["id"]).json()["estado"] == "EN_EVALUACION"


def test_linea_con_su_documentacion_y_datos(client):
    h = _auth(client)
    pid = _pers_id(client, h)
    _configurar_requisitos(pid, SALUD)
    req = client.get(f"{URL}/requisitos/{pid}", headers=h).json()
    assert [d["tipo"] for d in req["documentos"]] == ["DNI_FRENTE", "ORDEN_MEDICA", "PRESUPUESTO"]
    assert [c["codigo"] for c in req["campos"]] == ["COBERTURA", "TRATAMIENTO"]

    # Los datos obligatorios de la línea se piden al cargarla, como en el portal.
    base = {"producto_id": pid, "monto_solicitado": 1_000_000, "plazo_solicitado": 24, "solicitante_tipo": "REGISTRADO",
            "cliente_id": client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]}
    r = client.post(URL, headers=h, json=base)
    assert r.status_code == 422 and "Obra social" in r.text
    r = client.post(URL, headers=h, json={**base, "respuestas": {"COBERTURA": ["Otra"]}})
    assert r.status_code == 422
    s = _crear(client, h, respuestas={"COBERTURA": ["PAMI"], "TRATAMIENTO": ["Óptica", "Cirugía"]},
               datos_adicionales={"requisitos": [{"codigo": "TRUCHO", "valores": ["x"]}]})
    assert s["datosAdicionales"]["requisitos"] == [
        {"codigo": "COBERTURA", "etiqueta": "Obra social", "tipo": "UNICA", "valores": ["PAMI"]},
        {"codigo": "TRATAMIENTO", "etiqueta": "Tipo de tratamiento", "tipo": "MULTIPLE", "valores": ["Cirugía", "Óptica"]}]

    # El presupuesto es opcional: con DNI y orden médica alcanza.
    assert _adjuntar(client, h, s["id"], "RECIBO").status_code == 422
    assert _adjuntar(client, h, s["id"], "DNI_FRENTE").status_code == 201
    r = _enviar_a_evaluacion(client, h, s["id"])
    assert r.status_code == 409 and "Orden médica" in r.text
    assert _adjuntar(client, h, s["id"], "orden_medica", b"%PDF-1.4 x", "application/pdf", "orden.pdf").status_code == 201
    assert _enviar_a_evaluacion(client, h, s["id"]).json()["estado"] == "EN_EVALUACION"


def test_en_evaluacion_se_reemplaza_y_no_se_quita(client):
    h = _auth(client)
    _parametro(client, h, "DNI_FRENTE")
    s = _crear(client, h)
    primero = _adjuntar(client, h, s["id"], "DNI_FRENTE", nombre="dni-viejo.png").json()
    # En borrador se puede quitar; sin él, no se envía.
    assert client.delete(f"{URL}/{s['id']}/documentos/{primero['id']}", headers=h).status_code == 200
    assert _enviar_a_evaluacion(client, h, s["id"]).status_code == 409
    primero = _adjuntar(client, h, s["id"], "DNI_FRENTE", nombre="dni-viejo.png").json()
    assert _enviar_a_evaluacion(client, h, s["id"]).status_code == 200

    assert client.delete(f"{URL}/{s['id']}/documentos/{primero['id']}", headers=h).status_code == 409
    nuevo = _adjuntar(client, h, s["id"], "DNI_FRENTE", nombre="dni-nuevo.png")
    assert nuevo.status_code == 201
    items = client.get(f"{URL}/{s['id']}/documentos", headers=h).json()["items"]
    assert [d["nombre"] for d in items] == ["dni-nuevo.png"]


def test_resuelta_ya_no_se_toca(client):
    h = _auth(client)
    _parametro(client, h, "DNI_FRENTE")
    s = _crear(client, h)
    client.post(f"{URL}/{s['id']}/estado", headers=h, json={"accion": "anular", "motivo": "x"})
    assert _adjuntar(client, h, s["id"], "DNI_FRENTE").status_code == 409


def test_la_del_portal_la_documenta_el_solicitante(client):
    hp, h = _ingresar(client), _auth(client)
    numero = _enviar(client, hp, _un_producto(client, hp)).json()["numero"]
    s = next(x for x in client.get(URL, headers=h).json()["items"] if x["numero"] == numero)
    assert client.get(f"{URL}/{s['id']}/documentos", headers=h).json()["puedeAdjuntar"] is False
    r = _adjuntar(client, h, s["id"], "DNI_FRENTE")
    assert r.status_code == 409 and "observala" in r.text


def test_valida_el_archivo_y_el_permiso(client):
    h = _auth(client)
    s = _crear(client, h)
    r = _adjuntar(client, h, s["id"], "DNI_FRENTE", b"no es un pdf", "application/pdf", "dni.pdf")
    assert r.status_code == 422 and "no es la imagen o el PDF" in r.text
    assert _adjuntar(client, h, s["id"], "DNI_FRENTE", b"hola", "text/plain", "dni.txt").status_code == 422
    assert _adjuntar(client, _auth(client, "caja", "caja123"), s["id"], "DNI_FRENTE").status_code == 403
