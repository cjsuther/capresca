"""Solicitudes de crédito (línea nueva): alta registrado/express, workflow cuatro-ojos, originación."""
import pytest
from fastapi.testclient import TestClient
from tests.resolucion import otorgar


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
    body = {"producto_id": prod, "cliente_nombre": "SOLIC", "monto": 1_000_000, "plazo": 24, "solicitud_pp_id": sid}
    # Sin resolución de Despacho no se origina, aunque esté aprobada.
    sin = client.post("/api/creditos/contratos/originar", headers=hadmin, json=body)
    assert sin.status_code == 409 and "resolución" in sin.json()["detail"], sin.text
    assert client.get(f"/api/creditos/solicitudes/{sid}", headers=hadmin).json()["resolucion"] is None
    otorgar(sid, 45)
    assert client.get(f"/api/creditos/solicitudes/{sid}", headers=hadmin).json()["resolucion"]["numero"] == 45
    r = client.post("/api/creditos/contratos/originar", headers=hadmin, json=body)
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


def test_el_listado_trae_dni_y_cuil_y_se_busca_por_ambos(client):
    h = _auth(client)
    client.post("/api/creditos/solicitudes", headers=h, json=_base(
        client, h, solicitante_tipo="NO_REGISTRADO", cliente_id=None,
        cliente_datos={"apellido_nombre": "CUIL, PRUEBA", "cuil": "27-30999888-4", "dni": "30999888"}))

    todas = client.get("/api/creditos/solicitudes", headers=h).json()["items"]
    fila = next(i for i in todas if i["clienteNombre"] == "CUIL, PRUEBA")
    assert (fila["clienteDni"], fila["clienteCuil"]) == ("30999888", "27-30999888-4")
    assert all("clienteDni" in i for i in todas)
    # Se encuentra por DNI y por CUIL, con o sin guiones.
    for q in ("30999888", "27309998884", "30999888-4"):
        hallados = client.get("/api/creditos/solicitudes", headers=h, params={"q": q}).json()["items"]
        assert [i["clienteNombre"] for i in hallados] == ["CUIL, PRUEBA"]


# ---- Alta desde el backoffice con los datos del padrón (sueldo, cuotas y CBU como en el portal) ----
FICHA_PADRON = {"nombre": "LOPEZ, MARIA", "documento": "27303030309", "domicilio": "", "localidad": "",
                "telefono": "", "email": "", "cbu": "0110599520000001234567", "activo": True,
                "fecha_nacimiento": "1980-05-10", "sueldo": 1500000.0, "fecha_ingreso": "2010-03-01"}


def test_la_solicitud_se_precarga_con_los_datos_del_padron(client, monkeypatch):
    from app.core import clientes_padron
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: dict(FICHA_PADRON, client_id=cid))
    h = _auth(client)
    d = client.get("/api/creditos/solicitudes/datos-cliente/880", headers=h)
    assert d.status_code == 200, d.text
    d = d.json()
    assert d["fecha_nacimiento"] == "1980-05-10" and d["sueldo"] == 1500000.0
    assert d["cbu"] == "0110599520000001234567" and d["antiguedad_meses"] >= 12 * 16


def test_una_fecha_imposible_del_padron_no_se_precarga(client, monkeypatch):
    from app.core import clientes_padron
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: dict(FICHA_PADRON, client_id=cid,
                                                                   fecha_nacimiento="7987-04-12", cbu="123"))
    d = client.get("/api/creditos/solicitudes/datos-cliente/881", headers=_auth(client)).json()
    assert d["fecha_nacimiento"] is None and d["cbu"] is None


def test_cuanto_puede_pedir_con_el_sueldo(client):
    h = _auth(client)
    pid = _pers_id(client, h)
    r = client.post("/api/creditos/solicitudes/pre-aprobado", headers=h,
                    json={"producto_id": pid, "plazo": 24, "sueldo": 800000})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["monto_maximo"] > 0 and p["afectacion"] <= p["afectacion_max"]
    # La simulación con ese monto y el sueldo informa la misma afectación.
    sim = client.post(f"/api/creditos/productos/{pid}/simular-preview", headers=h,
                      json={"monto": p["monto_maximo"], "plazo": 24, "sueldo": 800000}).json()
    assert sim["afectacion"] == p["afectacion"]


def test_el_cbu_tiene_que_tener_22_digitos(client):
    h = _auth(client)
    r = client.post("/api/creditos/solicitudes", headers=h,
                    json=_base(client, h, datos_adicionales={"cbu": "0110 5995 2000"}))
    assert r.status_code == 422 and "22 dígitos" in r.json()["detail"]


def test_la_solicitud_del_backoffice_con_cbu_entra_a_un_lote_al_aprobarse(client):
    h = _auth(client)
    cbu = "0110599520000001234567"
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(
        client, h, datos_adicionales={"cbu": "0110-5995-2000-0001-2345-67", "sueldo_declarado": 3000000})).json()
    assert s["datosAdicionales"]["cbu"] == cbu
    client.post(f"/api/creditos/solicitudes/{s['id']}/estado", headers=h, json={"accion": "enviar"})
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/estado", headers=h, json={"accion": "aprobar"})
    assert r.status_code == 200 and r.json()["estado"] == "APROBADA"
    assert r.json()["lote"] and r.json()["lote"]["estado"] == "ABIERTO"


# ---- Modificar una solicitud en curso ----
def test_en_evaluacion_se_corrige_y_queda_quien_y_cuando(client):
    _activar_wf("SOLICITUD")
    hcred, hadmin = _auth(client, "creditos", "cred123"), _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=hcred, json=_base(client, hcred)).json()
    client.post(f"/api/creditos/solicitudes/{s['id']}/estado", headers=hcred, json={"accion": "enviar"})
    r = client.put(f"/api/creditos/solicitudes/{s['id']}", headers=hadmin,
                   json={"cbu": "0110599520000001234567", "plazo_solicitado": 36, "sueldo": 2500000})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["estado"] == "EN_EVALUACION" and d["plazo"] == 36
    assert d["datosAdicionales"]["cbu"] == "0110599520000001234567"
    assert d["datosAdicionales"]["sueldo_declarado"] == 2500000
    u = d["ultimaModificacion"]
    assert u["por"] == "admin" and u["en"] and sorted(u["campos"]) == ["cbu", "plazo", "sueldo"]
    assert u["cambios"]["plazo"] == {"antes": 24, "despues": 36}
    assert u["cambios"]["cbu"]["antes"] in (None, "") and u["cambios"]["cbu"]["despues"] == "0110599520000001234567"
    assert d["monto"] == 1_000_000, "lo que no se manda no se toca"
    assert d["evaluacion"]["cuota_estimada"] != s["evaluacion"]["cuota_estimada"]


def test_la_modificacion_queda_en_la_auditoria(client):
    from app import models
    from app.core.database import SessionLocal
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()
    client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h, json={"monto_solicitado": 900_000})
    with SessionLocal() as db:
        a = (db.query(models.AuditoriaCambio).filter_by(entidad="Solicitud", entidad_id=s["numero"])
             .order_by(models.AuditoriaCambio.id.desc()).first())
        assert a.operacion == "MODIFICACION" and a.usuario == "admin"
        assert a.datos_anteriores["monto"] == 1_000_000 and a.datos_nuevos["monto"] == 900_000


def test_aprobada_ya_no_se_modifica(client):
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()
    client.post(f"/api/creditos/solicitudes/{s['id']}/estado", headers=h, json={"accion": "enviar"})
    client.post(f"/api/creditos/solicitudes/{s['id']}/estado", headers=h, json={"accion": "aprobar"})
    r = client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h, json={"cbu": "0110599520000001234567"})
    assert r.status_code == 409


def test_la_modificacion_respeta_las_condiciones_de_la_linea(client):
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()
    r = client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h, json={"plazo_solicitado": 239})
    assert r.status_code == 422 and "condiciones" in r.json()["detail"]
    assert client.get(f"/api/creditos/solicitudes/{s['id']}", headers=h).json()["plazo"] == 24
    r = client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h, json={"cbu": "123"})
    assert r.status_code == 422


def test_sin_cambios_no_se_registra_nada(client):
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()
    r = client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h, json={"plazo_solicitado": 24})
    assert r.status_code == 200 and r.json()["ultimaModificacion"] is None


def test_el_historial_acumula_cada_modificacion_con_sus_valores(client):
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()
    client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h, json={"monto_solicitado": 900_000})
    d = client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h, json={"monto_solicitado": 800_000, "plazo_solicitado": 36}).json()
    hist = d["datosAdicionales"]["modificaciones"]
    assert [x["cambios"]["monto"] for x in hist] == [{"antes": 1_000_000, "despues": 900_000},
                                                     {"antes": 900_000, "despues": 800_000}]
    assert hist[1]["cambios"]["plazo"] == {"antes": 24, "despues": 36} and hist[1]["por"] == "admin"


def test_vacio_y_texto_vacio_no_cuentan_como_cambio(client):
    h = _auth(client)
    s = client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h)).json()
    d = client.put(f"/api/creditos/solicitudes/{s['id']}", headers=h,
                   json={"observaciones": "", "cbu": "0110599520000001234567"}).json()
    assert d["ultimaModificacion"]["campos"] == ["cbu"]


# ---- El cliente del portal que ya está en el padrón ----
def _ficha(cid, nombre="CONTRERAS, TERESA LAURA", documento="23486996"):
    return {"client_id": cid, "nombre": nombre, "documento": documento, "domicilio": "", "localidad": "",
            "telefono": "", "email": "", "cbu": "", "activo": True}


def _express(client, h, cuil="27234869960", dni="23486996"):
    return client.post("/api/creditos/solicitudes", headers=h, json=_base(
        client, h, solicitante_tipo="NO_REGISTRADO", cliente_id=None,
        cliente_datos={"apellido_nombre": "Contreras, Teresa Laura", "cuil": cuil, "dni": dni})).json()


def test_vincular_un_cliente_del_padron_que_no_esta_en_creditos(client, monkeypatch):
    """El buscador busca en el padrón de Clientes; antes el vínculo sólo miraba la copia local y daba 404."""
    from app.core import clientes_padron
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: _ficha(cid))
    h = _auth(client)
    s = _express(client, h)
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=h,
                    json={"cliente_id": 26797, "copiar_documentos": False})
    assert r.status_code == 200, r.text
    assert r.json()["solicitud"]["solicitanteTipo"] == "REGISTRADO" and r.json()["clienteId"] == 26797
    assert r.json()["solicitud"]["clienteNombre"] == "CONTRERAS, TERESA LAURA"


def test_el_detalle_sugiere_el_cliente_del_padron_por_dni_aunque_traiga_cuil(client, monkeypatch):
    from app.core import clientes_padron
    monkeypatch.setattr(clientes_padron, "ids_por_documento", lambda docs: {"23486996": 26797} if "23486996" in docs else {})
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: _ficha(cid))
    h = _auth(client)
    s = _express(client, h)
    d = client.get(f"/api/creditos/solicitudes/{s['id']}", headers=h).json()
    assert d["clienteEnPadron"] == {"id": 26797, "nombre": "CONTRERAS, TERESA LAURA", "documento": "23486996"}


def test_crear_cliente_no_duplica_al_que_ya_esta_con_el_otro_documento(client, monkeypatch):
    from app.core import clientes_padron
    monkeypatch.setattr(clientes_padron, "ids_por_documento", lambda docs: {"23486996": 26797} if "23486996" in docs else {})
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: _ficha(cid))
    monkeypatch.setattr(clientes_padron, "importar", lambda p: (_ for _ in ()).throw(AssertionError("no debía dar de alta")))
    h = _auth(client)
    s = _express(client, h)
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=h, json={"copiar_documentos": False})
    assert r.status_code == 200, r.text
    assert r.json()["clienteId"] == 26797 and r.json()["yaExistia"] is True


def test_sin_coincidencia_en_el_padron_no_sugiere_nada(client):
    h = _auth(client)
    s = _express(client, h, cuil="20111111119", dni="11111111")
    assert client.get(f"/api/creditos/solicitudes/{s['id']}", headers=h).json()["clienteEnPadron"] is None


def test_el_listado_dice_la_linea_de_cada_solicitud(client):
    h = _auth(client)
    client.post("/api/creditos/solicitudes", headers=h, json=_base(client, h))
    s = client.get("/api/creditos/solicitudes", headers=h).json()["items"][0]
    assert s["productoCodigo"] == "LP-PERS-01" and s["productoNombre"]
