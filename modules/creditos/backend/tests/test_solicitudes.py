"""Solicitudes de crédito (línea nueva): alta registrado/express, workflow cuatro-ojos, originación."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client, user="admin", pw="admin123"):
    r = client.post("/api/creditos/auth/login", data={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _pers_id(client, h):
    return next(p for p in client.get("/api/creditos/contratos/oferta", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")["id"]


def _activar_wf(objeto: str) -> None:
    """El cuatro-ojos se siembra INACTIVO (app nueva single-admin, H-141); los tests que ejercitan el
    workflow lo activan explícitamente en Configuraciones."""
    from tests.config_falsa import CONFIG
    CONFIG.activar(objeto)

def _cliente_id(client, h):
    return client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]


def _base(client, h, **kw):
    d = {"producto_id": _pers_id(client, h), "monto_solicitado": 1_000_000, "plazo_solicitado": 24,
         "solicitante_tipo": "REGISTRADO", "cliente_id": _cliente_id(client, h)}
    d.update(kw)
    return d


def test_crear_registrado_calcula_evaluacion(client):
    h = _auth(client)
    r = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h))
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["estado"] == "BORRADOR" and s["numero"].startswith("SOL-")
    assert s["evaluacion"]["elegible"] is True and s["evaluacion"]["cuota_estimada"] > 0


def test_alta_express_requiere_datos_minimos(client):
    h = _auth(client)
    # sin nombre/cuil -> 422
    bad = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h, solicitante_tipo="NO_REGISTRADO", cliente_id=None, cliente_datos={}))
    assert bad.status_code == 422
    ok = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h, solicitante_tipo="NO_REGISTRADO", cliente_id=None,
                                                               cliente_datos={"apellido_nombre": "GOMEZ, JUAN", "cuil": "20111111119", "dni": "11111111"}))
    assert ok.status_code == 201 and ok.json()["clienteNombre"] == "GOMEZ, JUAN"


def test_workflow_cuatro_ojos(client):
    _activar_wf("SOLICITUD")
    hcred, hadmin = _auth(client, "creditos", "cred123"), _auth(client)
    sid = client.post("/api/creditos/solicitudes", headers=hcred, json=_base(client, hcred)).json()["id"]
    # enviar a evaluación (créditos)
    r = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcred, json={"accion": "enviar"})
    assert r.json()["estado"] == "EN_EVALUACION"
    # el mismo que envió NO puede aprobar (cuatro-ojos) — pero créditos tampoco tiene perfil aprobador
    assert client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcred, json={"accion": "aprobar"}).status_code == 403
    # admin (distinto) aprueba
    r = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert r.status_code == 200 and r.json()["estado"] == "APROBADA" and r.json()["resueltaPor"] == "admin"


def test_aprobar_exige_rol_aun_con_workflow_inactivo(client):
    """H-153: con la regla SOLICITUD sembrada INACTIVA (app single-admin), resolver una solicitud NO debe
    quedar abierto a cualquiera. 'caja' (XCJ, sin rol aprobador) no puede aprobar ni rechazar (403);
    'admin' (aprobador) sí. Antes el motor auto-aprobaba sin mirar permisos → cualquiera resolvía."""
    hcred, hadmin, hcaja = _auth(client, "creditos", "cred123"), _auth(client), _auth(client, "caja", "caja123")
    sid = client.post("/api/creditos/solicitudes", headers=hcred, json=_base(client, hcred)).json()["id"]
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcred, json={"accion": "enviar"})
    # workflow inactivo (default) → caja NO puede aprobar ni rechazar
    assert client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcaja, json={"accion": "aprobar"}).status_code == 403
    assert client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcaja, json={"accion": "rechazar", "motivo": "x"}).status_code == 403
    # admin (rol aprobador) sí
    r = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert r.status_code == 200 and r.json()["estado"] == "APROBADA"


def test_cuatro_ojos_bloquea_autoaprobacion(client):
    _activar_wf("SOLICITUD")
    h = _auth(client)  # admin envía y quiere aprobar lo suyo
    sid = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()["id"]
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=h, json={"accion": "enviar"})
    assert client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=h, json={"accion": "aprobar"}).status_code == 409


def test_no_crear_solicitud_no_elegible(client):
    # H-202: si lo declarado NO cumple las condiciones de la línea (acá, monto fuera de rango), no se
    # puede pedir la solicitud: se rechaza al CREAR (bloqueo duro, mismo criterio que el portal).
    hcred = _auth(client, "creditos", "cred123")
    r = client.post("/api/creditos/solicitudes", headers=hcred, json=_base(client, hcred, monto_solicitado=50))
    assert r.status_code == 422, r.text
    assert "condiciones" in r.json()["detail"].lower()


def test_originar_desde_solicitud_aprobada(client):
    hcred, hadmin = _auth(client, "creditos", "cred123"), _auth(client)
    sid = client.post("/api/creditos/solicitudes", headers=hcred, json=_base(client, hcred)).json()["id"]
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hcred, json={"accion": "enviar"})
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hadmin, json={"accion": "aprobar"})
    prod = _pers_id(client, hadmin)
    r = client.post("/api/creditos/contratos/originar", headers=hadmin,
                    json={"producto_id": prod, "cliente_nombre": "SOLIC", "monto": 1_000_000, "plazo": 24, "solicitud_pp_id": sid})
    assert r.status_code == 201, r.text
    # la solicitud queda ORIGINADA y ligada al contrato
    s = client.get(f"/api/creditos/solicitudes/{sid}", headers=hadmin).json()
    assert s["estado"] == "ORIGINADA" and s["contratoId"] == r.json()["id"]
    # no se puede originar dos veces
    dup = client.post("/api/creditos/contratos/originar", headers=hadmin,
                      json={"producto_id": prod, "cliente_nombre": "SOLIC", "monto": 1_000_000, "plazo": 24, "solicitud_pp_id": sid})
    assert dup.status_code == 409


def test_no_originar_solicitud_no_aprobada(client):
    h = _auth(client)
    sid = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()["id"]  # queda BORRADOR
    prod = _pers_id(client, h)
    r = client.post("/api/creditos/contratos/originar", headers=h,
                    json={"producto_id": prod, "cliente_nombre": "X", "monto": 1_000_000, "plazo": 24, "solicitud_pp_id": sid})
    assert r.status_code == 409


def test_promover_cliente_express_da_de_alta_en_el_padron(client, monkeypatch):
    """La express se promueve dando de alta a la persona en el PADRÓN (módulo Clientes); Créditos
    sólo espeja. No hay maestro de personas propio."""
    from app.core import clientes_padron
    pedidos = []

    def _importar(personas):
        pedidos.append(personas)
        return {"creados": {personas[0]["documento"]: 4321}, "existentes": {}}

    monkeypatch.setattr(clientes_padron, "importar", _importar)
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: {
        "client_id": cid, "nombre": "PEREZ, ANA", "documento": "27222222229",
        "domicilio": "", "localidad": "", "telefono": "", "email": "", "cbu": "", "activo": True})

    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h, solicitante_tipo="NO_REGISTRADO", cliente_id=None,
                                                              cliente_datos={"apellido_nombre": "PEREZ, ANA", "cuil": "27222222229", "dni": "22222222"})).json()
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=h, json={})
    assert r.status_code == 200, r.text
    assert r.json()["solicitud"]["solicitanteTipo"] == "REGISTRADO"
    assert r.json()["clienteId"] == 4321                  # el id es el que asignó el padrón
    assert pedidos and pedidos[0][0]["documento"] == "27222222229"

    cli = client.get("/api/creditos/clientes/4321", headers=h).json()
    assert cli["apellido_nombre"] == "PEREZ, ANA"


def test_promover_cliente_avisa_si_el_padron_no_responde(client, monkeypatch):
    from app.core import clientes_padron

    def _cae(_personas):
        raise clientes_padron.PadronNoDisponible("connection refused")

    monkeypatch.setattr(clientes_padron, "importar", _cae)
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h, solicitante_tipo="NO_REGISTRADO", cliente_id=None,
                                                              cliente_datos={"apellido_nombre": "SOSA, RAUL", "cuil": "20333333339", "dni": "33333333"})).json()
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=h, json={})
    assert r.status_code == 503 and "padrón" in r.json()["detail"].lower()


def test_promover_vincular_cliente_existente(client):
    """H-170: una express se puede VINCULAR a un cliente que ya existe en el maestro (alta hecha en
    Clientes → Maestro), pasando cliente_id — no crea uno nuevo."""
    h = _auth(client)
    cid = _cliente_id(client, h)   # un cliente del maestro
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h, solicitante_tipo="NO_REGISTRADO",
                    cliente_id=None, cliente_datos={"apellido_nombre": "GARCIA, LUIS", "dni": "30111222", "cuil": "20301112223"})).json()
    assert "id" in s, s
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=h, json={"cliente_id": cid})
    assert r.status_code == 200
    assert r.json()["clienteId"] == cid and r.json()["solicitud"]["solicitanteTipo"] == "REGISTRADO"
    # cliente inexistente -> 404
    assert client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=h, json={"cliente_id": 999999}).status_code in (404, 409)


def test_estado_guarda_observacion(client):
    """H-170: la observación del asesor al resolver queda registrada en datos_adicionales.obs_revision."""
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/estado", headers=h,
                    json={"accion": "anular", "observacion": "Duplicada de la SOL previa"}).json()
    assert r["estado"] == "ANULADA"
    assert r["datosAdicionales"]["obs_revision"] == "Duplicada de la SOL previa"


def test_permiso_carga(client):
    hcaja = _auth(client, "caja", "caja123")  # XCJ: no edita
    assert client.post("/api/creditos/solicitudes", headers=hcaja, json=_base(client, _auth(client))).status_code == 403
