"""Portal del ciudadano (Fase 1): SSO Mi Catamarca (mock), segregación de realms y simulador.

El proveedor real requiere credenciales por entorno; sin ellas se usa el MOCK determinista
(sin red, sin el WAF de Cloudflare), que es lo que ejercitan estos tests."""
import os
from datetime import date

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_portal.db"
os.environ["ENVIRONMENT"] = "development"

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _ingresar(client) -> dict:
    """Corre el flujo SSO mock y devuelve el header con el token de sesión del portal."""
    r = client.get("/api/creditos/portal/auth/login")
    assert r.status_code == 200 and r.json()["mock"] is True
    state = r.json()["authorize_url"].split("state=")[1]
    cb = client.get("/api/creditos/portal/auth/callback",
                    params={"code": "mock-code", "state": state}, follow_redirects=False)
    assert cb.status_code in (302, 307)
    loc = cb.headers["location"]
    assert "/ingreso#token=" in loc
    return {"Authorization": f"Bearer {loc.split('#token=')[1]}"}


def test_flujo_sso_mock_emite_sesion(client):
    h = _ingresar(client)
    me = client.get("/api/creditos/portal/me", headers=h).json()
    assert me["sub"] == "mc-demo-30123456"
    assert me["email"] and me["nombre"]


def test_mock_authorize_redirige_al_callback(client):
    state = client.get("/api/creditos/portal/auth/login").json()["authorize_url"].split("state=")[1]
    r = client.get("/api/creditos/portal/auth/mock-authorize", params={"state": state}, follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/api/creditos/portal/auth/callback" in r.headers["location"]
    assert "code=mock-code" in r.headers["location"]


def test_state_invalido_rechazado(client):
    r = client.get("/api/creditos/portal/auth/callback",
                   params={"code": "x", "state": "no-es-un-state"}, follow_redirects=False)
    assert r.status_code == 400


def test_state_no_reutilizable(client):
    """H-158: el state OIDC es de un solo uso. Un segundo callback con el mismo state (replay dentro de la
    ventana de validez) se rechaza (400), aunque el JWT siga firmado y sin expirar."""
    state = client.get("/api/creditos/portal/auth/login").json()["authorize_url"].split("state=")[1]
    r1 = client.get("/api/creditos/portal/auth/callback", params={"code": "mock-code", "state": state}, follow_redirects=False)
    assert r1.status_code in (302, 307)   # primer uso: OK (redirect con token)
    r2 = client.get("/api/creditos/portal/auth/callback", params={"code": "mock-code", "state": state}, follow_redirects=False)
    assert r2.status_code == 400          # replay: rechazado


def test_realms_separados(client):
    """Un token de portal NO abre el backoffice; un token interno NO abre el portal."""
    h_portal = _ingresar(client)
    # Portal → interno: rechazado.
    assert client.get("/api/creditos/creditos/lineas", headers=h_portal).status_code == 401
    # Interno → portal: rechazado.
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    h_int = {"Authorization": f"Bearer {tok}"}
    assert client.get("/api/creditos/portal/me", headers=h_int).status_code == 401
    # Sin token: rechazado.
    assert client.get("/api/creditos/portal/me").status_code == 401


def test_simulador_usa_producto_nuevo_y_motor_unico(client):
    """El simulador del portal corre sobre PRODUCTOS PUBLICADOS (product builder) y usa el mismo
    `cronograma` que la simulación/originación del backoffice: mismo total (simulado == contratado)."""
    h = _ingresar(client)
    prods = client.get("/api/creditos/portal/productos", headers=h).json()
    assert prods, "debe haber al menos un producto PUBLICADO y vigente"
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    # Para CADA producto publicado (incluida la tasa variable): portal == simulación pp interna.
    for p in prods:
        assert p["tna"] >= 0
        monto = min(max(500000.0, p["monto_min"]), p["monto_max"])
        plazo = min(max(12, p["plazo_min"]), p["plazo_max"])
        sim_portal = client.post("/api/creditos/portal/simular", headers=h,
                                 json={**CONSENT, "producto_id": p["id"], "monto": monto, "plazo": plazo}).json()
        assert sim_portal["cantidad_cuotas"] == plazo
        assert sim_portal["total_a_pagar"] > 0
        sim_int = client.post(f"/api/creditos/productos/{p['id']}/simulaciones", headers=hi,
                              json={"monto": monto, "plazo": plazo}).json()
        # Mismo motor y misma TNA base (fija o índice+margen) → mismo total al centavo.
        assert round(sim_portal["total_a_pagar"], 2) == round(sim_int["totalCuotas"], 2)


def test_login_no_requiere_token(client):
    assert client.get("/api/creditos/portal/auth/login").status_code == 200


def _un_producto(client, h):
    return client.get("/api/creditos/portal/productos", headers=h).json()[0]


# CBU + consentimientos + identidad declarada, obligatorios para enviar (se ignoran en /simular). H-162.
VIDEOS = ["video1", "video2", "video3"]   # los obligatorios por defecto (config `portal_videos`)
# La solicitud pide fecha de nacimiento (la edad se calcula) y contacto del ciudadano.
NACIMIENTO_40 = f"{date.today().year - 40}-01-01"
CONSENT = {"cbu": "2850590940090418135201", "acepta_terminos": True, "acepta_datos": True,
           "apellido": "PEREZ", "nombre": "JUAN CARLOS", "dni": "30123456", "videos_vistos": VIDEOS,
           "fecha_nacimiento": NACIMIENTO_40, "email": "juan@example.com", "telefono": "3834123456"}


def test_videos_obligatorios_del_paso_4(client):
    """El portal lista los videos que hay que ver completos antes de confirmar."""
    h = _ingresar(client)
    vs = client.get("/api/creditos/portal/videos", headers=h).json()
    assert [v["id"] for v in vs] == VIDEOS
    assert vs[0] == {"id": "video1", "titulo": "Video 1", "url": "/portal-creditos/videos/video1.mp4"}
    assert client.get("/api/creditos/portal/videos").status_code == 401   # sólo con sesión del ciudadano


def test_no_se_envia_sin_ver_todos_los_videos(client):
    """Aunque se llame a la API salteando el portal, sin los tres videos vistos no hay solicitud; con
    ellos, queda registrado en la solicitud que los vio (auditoría)."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    base = {**CONSENT, "producto_id": p["id"], "monto": 500000.0, "plazo": 12}
    for vistos in ([], ["video1", "video2"], ["video1", "video2", "otro"]):
        r = client.post("/api/creditos/portal/solicitudes", headers=h, json={**base, "videos_vistos": vistos})
        assert r.status_code == 422 and "videos" in r.json()["detail"]
    r = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "vid-ok"}, json=base)
    assert r.status_code == 201, r.text
    from app.core.database import SessionLocal
    from app import models_productos as _m
    with SessionLocal() as db:
        sol = db.query(_m.PPSolicitud).filter_by(numero=r.json()["numero"]).one()
        assert sol.datos_adicionales["videos_vistos"]["videos"] == VIDEOS


def test_sin_videos_configurados_no_se_exigen(client, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "portal_videos", "")
    h = _ingresar(client)
    assert client.get("/api/creditos/portal/videos", headers=h).json() == []
    p = _un_producto(client, h)
    r = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "vid-none"},
                    json={**CONSENT, "videos_vistos": [], "producto_id": p["id"], "monto": 500000.0, "plazo": 12})
    assert r.status_code == 201, r.text


def test_enviar_exige_identidad_declarada(client):
    """H-162: Mi Catamarca sólo confirma que la persona existe; el ciudadano DECLARA apellido/nombre/DNI.
    Enviar sin ellos (o con DNI inválido) da 422; el DNI declarado queda en cliente_datos."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    base = {"cbu": "2850590940090418135201", "acepta_terminos": True, "acepta_datos": True,
            "producto_id": p["id"], "monto": 500000.0, "plazo": 12, "videos_vistos": VIDEOS,
            "fecha_nacimiento": NACIMIENTO_40, "email": "ana@example.com", "telefono": "3834765432"}
    # sin apellido/nombre → 422
    assert client.post("/api/creditos/portal/solicitudes", headers=h, json=base).status_code == 422
    # DNI inválido → 422
    assert client.post("/api/creditos/portal/solicitudes", headers=h,
                       json={**base, "apellido": "GOMEZ", "nombre": "ANA", "dni": "123"}).status_code == 422
    # completo → 201, con la identidad declarada (apellido, nombre) y DNI normalizado
    r = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "idc-1"},
                    json={**base, "apellido": "GOMEZ", "nombre": "ANA", "dni": "27.345.678"})
    assert r.status_code == 201, r.text
    numero = r.json()["numero"]
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    s = next(x for x in client.get("/api/creditos/solicitudes", headers={"Authorization": f"Bearer {tok}"}).json()["items"]
             if x["numero"] == numero)
    assert s["clienteDatos"]["apellido_nombre"] == "GOMEZ, ANA" and s["clienteDatos"]["dni"] == "27345678"


def test_ciudadano_envia_solicitud_cae_en_inbox(client):
    """Fase 2: el ciudadano envía la solicitud → PPSolicitud EN_EVALUACION en el Inbox del backoffice."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    monto = min(max(500000.0, p["monto_min"]), p["monto_max"])
    plazo = min(max(12, p["plazo_min"]), p["plazo_max"])

    r = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "sol-portal-1"},
                    json={**CONSENT, "producto_id": p["id"], "monto": monto, "plazo": plazo})
    assert r.status_code == 201, r.text
    sol = r.json()
    assert sol["estado"] == "EN_EVALUACION" and sol["numero"].startswith("SOL-")
    assert sol["cuota_estimada"] > 0   # la cuota que vio al simular queda guardada (no depende de elegibilidad)

    # El ciudadano ve la suya en "mis solicitudes".
    mias = client.get("/api/creditos/portal/solicitudes", headers=h).json()
    assert any(s["numero"] == sol["numero"] for s in mias)

    # Aparece en el backoffice: listado de solicitudes y en el Inbox de aprobaciones.
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    back = client.get("/api/creditos/solicitudes", headers=hi, params={"estado": "EN_EVALUACION"}).json()
    match = next(s for s in back["items"] if s["numero"] == sol["numero"])
    assert match["origen"] == "PORTAL" and match["estado"] == "EN_EVALUACION"
    inbox = client.get("/api/creditos/aprobaciones/inbox", headers=hi).json()
    assert any(str(sol["numero"]) in str(it) for it in inbox.get("items", inbox if isinstance(inbox, list) else []))


def test_envio_solicitud_es_idempotente(client):
    """Un doble-clic con la misma Idempotency-Key crea UNA sola solicitud."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    body = {**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
            "plazo": min(max(12, p["plazo_min"]), p["plazo_max"])}
    hk = {**h, "Idempotency-Key": "sol-dup-1"}
    n1 = client.post("/api/creditos/portal/solicitudes", headers=hk, json=body).json()["numero"]
    n2 = client.post("/api/creditos/portal/solicitudes", headers=hk, json=body).json()["numero"]
    assert n1 == n2
    assert len(client.get("/api/creditos/portal/solicitudes", headers=h).json()) == 1


def test_solicitud_guarda_destino(client):
    """El destino del crédito (opcional) se normaliza a su código, se persiste y el detalle lo muestra
    con su etiqueta; un destino desconocido se ignora (queda vacío)."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    base = {**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
            "plazo": min(max(12, p["plazo_min"]), p["plazo_max"])}
    # 'vivienda' (minúsculas) → VIVIENDA → etiqueta.
    n1 = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "dest-ok"},
                     json={**base, "destino": "vivienda"}).json()["numero"]
    assert client.get(f"/api/creditos/portal/solicitudes/{n1}", headers=h).json()["destino"] == "Vivienda / refacción"
    # Destino desconocido → se ignora (detalle vacío).
    n2 = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "dest-bad"},
                     json={**base, "destino": "lo-que-sea"}).json()["numero"]
    assert client.get(f"/api/creditos/portal/solicitudes/{n2}", headers=h).json()["destino"] == ""


def test_mis_creditos_y_notificaciones(client):
    """Punto 2: el ciudadano ve el crédito otorgado (a partir de su solicitud), sus cuotas y notificaciones."""
    h = _ingresar(client)
    # Producto WEB-elegible para empleado público (Personal Flexible): el ciudadano envía la solicitud.
    prods = client.get("/api/creditos/portal/productos", headers=h).json()
    p = next((x for x in prods if "Flexible" in x["nombre"]), None)
    if p is None:
        import pytest as _pt; _pt.skip("no hay producto WEB-elegible sembrado")
    body = {**CONSENT, "producto_id": p["id"], "monto": 500000.0, "plazo": min(max(12, p["plazo_min"]), p["plazo_max"]),
            "segmento": "AGENTE_PUBLICO", "fecha_nacimiento": f"{date.today().year - 40}-01-01"}
    numero = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "mc-1"}, json=body).json()["numero"]

    # Antes de originar: no hay créditos.
    assert client.get("/api/creditos/portal/creditos", headers=h).json() == []

    # Backoffice: aprobar la solicitud del portal y originarla como contrato.
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    sid = next(s for s in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if s["numero"] == numero)["id"]
    # H-203: el cliente del portal es NO_REGISTRADO → hay que darlo de alta en el maestro antes de aprobar.
    client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={})
    ap = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hi, json={"accion": "aprobar"})
    assert ap.status_code == 200 and ap.json()["estado"] == "APROBADA", ap.text
    orig = client.post("/api/creditos/contratos/originar", headers=hi, json={
        "producto_id": p["id"], "cliente_nombre": "JUAN CARLOS PEREZ", "monto": 500000, "plazo": body["plazo"],
        "solicitud_pp_id": sid, "desembolsar": True})
    assert orig.status_code == 201, orig.text

    # El ciudadano ve su crédito, sus cuotas y sus notificaciones.
    creds = client.get("/api/creditos/portal/creditos", headers=h).json()
    assert len(creds) == 1
    cr = creds[0]
    assert cr["cuotas_total"] == body["plazo"] and cr["proxima"] is not None
    det = client.get(f"/api/creditos/portal/creditos/{cr['contrato']}", headers=h).json()
    assert len(det["cuotas"]) == body["plazo"] and all("estado" in q for q in det["cuotas"])
    notis = client.get("/api/creditos/portal/notificaciones", headers=h).json()
    assert any(n["tipo"] == "otorgado" for n in notis)
    # Owner-scoping: un crédito inexistente/ajeno → 404.
    assert client.get("/api/creditos/portal/creditos/CTO-9999-99999", headers=h).status_code == 404


def test_originacion_web_es_revision_y_bloquea_sin_datos(client):
    """Canal web (H-134): la originación es una revisión. La solicitud llega con identidad (DNI de
    Mi Catamarca) + CBU → 'lista para liquidar'. Si falta un dato obligatorio, originar se bloquea (422)."""
    h = _ingresar(client)
    prods = client.get("/api/creditos/portal/productos", headers=h).json()
    p = next((x for x in prods if "Flexible" in x["nombre"]), None)
    if p is None:
        import pytest as _pt; _pt.skip("no hay producto WEB-elegible sembrado")
    body = {**CONSENT, "producto_id": p["id"], "monto": 500000.0, "plazo": min(max(12, p["plazo_min"]), p["plazo_max"]),
            "segmento": "AGENTE_PUBLICO", "fecha_nacimiento": f"{date.today().year - 40}-01-01"}
    numero = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "rev-1"}, json=body).json()["numero"]

    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    s = next(x for x in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if x["numero"] == numero)
    sid = s["id"]
    # Revisión: aplica al canal web, viene el DNI de Mi Catamarca y el CBU → lista para liquidar.
    dl = s["datosLiquidacion"]
    assert dl["aplica"] is True and dl["lista"] is True, dl
    assert s["clienteDatos"]["dni"] == "30123456"      # el documento de Mi Catamarca viajó (ya no vacío)
    # H-203: registrar el cliente en el maestro (alta) antes de aprobar.
    client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={})
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hi, json={"accion": "aprobar"})

    # Si se pierde un dato obligatorio (el DNI del cliente en el maestro), la originación se bloquea.
    from app.core.database import SessionLocal
    from app import models_productos as _m
    from app import models as _mm
    with SessionLocal() as db:
        sol = db.query(_m.PPSolicitud).filter_by(numero=numero).first()
        cli = db.get(_mm.Cliente, sol.cliente_id)
        cli.dni = ""; db.commit()
    blocked = client.post("/api/creditos/contratos/originar", headers=hi, json={
        "producto_id": p["id"], "cliente_nombre": "JUAN CARLOS PEREZ", "monto": 500000, "plazo": body["plazo"],
        "solicitud_pp_id": sid, "desembolsar": True})
    assert blocked.status_code == 422 and "DNI" in blocked.json()["detail"], blocked.text


def test_originacion_deja_a_liquidar_y_lote_desembolsa(client):
    """H-135: originar desde una solicitud (canal web) deja el contrato A_LIQUIDAR aunque se pida
    desembolsar; el lote de liquidación lo agrupa por día y al liquidarlo pasa a ACTIVO."""
    h = _ingresar(client)
    p = next((x for x in client.get("/api/creditos/portal/productos", headers=h).json() if "Flexible" in x["nombre"]), None)
    if p is None:
        import pytest as _pt; _pt.skip("sin producto WEB-elegible")
    body = {**CONSENT, "producto_id": p["id"], "monto": 500000.0, "plazo": 12, "segmento": "AGENTE_PUBLICO", "fecha_nacimiento": f"{date.today().year - 40}-01-01"}
    numero = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "lote-t"}, json=body).json()["numero"]
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    sid = next(s for s in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if s["numero"] == numero)["id"]
    client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={})   # H-203: alta en maestro antes de aprobar
    client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hi, json={"accion": "aprobar"})
    cto = client.post("/api/creditos/contratos/originar", headers=hi, json={
        "producto_id": p["id"], "cliente_nombre": "JUAN CARLOS PEREZ", "monto": 500000, "plazo": 12,
        "segmento": "AGENTE_PUBLICO", "canal": "WEB", "solicitud_pp_id": sid, "desembolsar": True}).json()
    # Aunque se pida desembolsar, al venir de una solicitud el contrato queda A_LIQUIDAR (no se desembolsa).
    assert cto["estado"] == "A_LIQUIDAR", cto

    hoy = date.today().isoformat()
    lote = next(l for l in client.get("/api/creditos/contratos/lotes-liquidacion", headers=hi).json()["items"] if l["fecha"] == hoy)
    assert any(c["numero"] == cto["numero_contrato"] for c in lote["contratos"])

    r = client.post("/api/creditos/contratos/liquidar-lote", headers=hi, json={"fecha": hoy}).json()
    assert cto["numero_contrato"] in r["desembolsados"], r
    assert client.get(f"/api/creditos/contratos/{cto['id']}", headers=hi).json()["estado"] == "ACTIVO"


def test_alta_maestro_completa_cuil(client, monkeypatch):
    """H-137: el alta de una solicitud express valida el CUIL (11 díg.) y da de alta a la persona en el
    PADRÓN (módulo Clientes) con el CUIL/DNI que confirmó el asesor; la solicitud pasa a REGISTRADA."""
    from app.core import clientes_padron
    monkeypatch.setattr(clientes_padron, "importar",
                        lambda personas: {"creados": {personas[0]["documento"]: 5501}, "existentes": {}})
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: {
        "client_id": cid, "nombre": "JUAN CARLOS PEREZ", "documento": "20301234567",
        "domicilio": "", "localidad": "", "telefono": "", "email": "", "cbu": "", "activo": True})
    h = _ingresar(client)
    p = _un_producto(client, h)
    body = {**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
            "plazo": min(max(12, p["plazo_min"]), p["plazo_max"])}
    numero = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "alta-t"}, json=body).json()["numero"]
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    s = next(x for x in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if x["numero"] == numero)
    assert s["solicitanteTipo"] == "NO_REGISTRADO" and s["clienteDatos"]["dni"] == "30123456"
    # CUIL inválido → 422.
    bad = client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=hi, json={"cuil": "123"})
    assert bad.status_code == 422 and "CUIL" in bad.json()["detail"]
    # CUIL válido (con guiones) → cliente registrado con cuil/dni normalizados.
    r = client.post(f"/api/creditos/solicitudes/{s['id']}/promover-cliente", headers=hi,
                    json={"cuil": "20-30123456-7", "dni": "30123456", "apellido_nombre": "JUAN CARLOS PEREZ"})
    assert r.status_code == 200 and r.json()["solicitud"]["solicitanteTipo"] == "REGISTRADO", r.text
    cid = r.json()["clienteId"]
    from app.core.database import SessionLocal
    from app import models as _mm
    assert cid == 5501                                   # el id lo asigna el padrón
    with SessionLocal() as db:
        cli = db.get(_mm.Cliente, cid)                   # y acá queda el espejo
        assert cli.cuil == "20301234567" and cli.apellido_nombre == "JUAN CARLOS PEREZ"


def test_no_aprobar_cliente_no_registrado(client):
    """H-203: una solicitud de cliente NO registrado (portal/express) no se puede aprobar hasta darlo de
    alta en el maestro (o vincular uno existente); recién ahí se aprueba."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    body = {**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
            "plazo": min(max(12, p["plazo_min"]), p["plazo_max"])}
    numero = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "noreg-t"}, json=body).json()["numero"]
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    sid = next(s for s in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if s["numero"] == numero)["id"]
    r = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hi, json={"accion": "aprobar"})
    assert r.status_code == 409 and "registrado" in r.json()["detail"].lower(), r.text
    client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={})
    ok = client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hi, json={"accion": "aprobar"})
    assert ok.status_code == 200 and ok.json()["estado"] == "APROBADA", ok.text


def test_lote_marca_pendientes_de_aprobacion(client):
    """H-139: con el workflow DESEMBOLSO activo, liquidar el lote deja los contratos esperando aprobación
    (no se desembolsan) y el lote los marca `pendienteAprobacion`."""
    h = _ingresar(client)
    p = next((x for x in client.get("/api/creditos/portal/productos", headers=h).json() if "Flexible" in x["nombre"]), None)
    if p is None:
        import pytest as _pt; _pt.skip("sin producto WEB-elegible")
    from tests.config_falsa import CONFIG
    CONFIG.activar("DESEMBOLSO")   # regla del workflow, en Configuraciones
    try:
        body = {**CONSENT, "producto_id": p["id"], "monto": 500000.0, "plazo": 12, "segmento": "AGENTE_PUBLICO", "fecha_nacimiento": f"{date.today().year - 40}-01-01"}
        numero = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "pend-t"}, json=body).json()["numero"]
        tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
        hi = {"Authorization": f"Bearer {tok}"}
        sid = next(s for s in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if s["numero"] == numero)["id"]
        client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={})   # H-203: alta en maestro antes de aprobar
        client.post(f"/api/creditos/solicitudes/{sid}/estado", headers=hi, json={"accion": "aprobar"})
        cto = client.post("/api/creditos/contratos/originar", headers=hi, json={
            "producto_id": p["id"], "cliente_nombre": "JUAN CARLOS PEREZ", "monto": 500000, "plazo": 12,
            "segmento": "AGENTE_PUBLICO", "canal": "WEB", "solicitud_pp_id": sid}).json()
        hoy = date.today().isoformat()
        res = client.post("/api/creditos/contratos/liquidar-lote", headers=hi, json={"fecha": hoy}).json()
        assert cto["numero_contrato"] in res["pendientesAprobacion"]
        assert cto["numero_contrato"] not in res["desembolsados"]
        lote = next(l for l in client.get("/api/creditos/contratos/lotes-liquidacion", headers=hi).json()["items"] if l["fecha"] == hoy)
        ct = next(x for x in lote["contratos"] if x["numero"] == cto["numero_contrato"])
        assert ct["pendienteAprobacion"] is True and lote["pendientes"] >= 1
        assert client.get(f"/api/creditos/contratos/{cto['id']}", headers=hi).json()["estado"] == "A_LIQUIDAR"
    finally:
        CONFIG.activar("DESEMBOLSO", False)


def test_pre_aprobado_respeta_afectacion(client):
    """El pre-aprobado devuelve el mayor monto cuya cuota no supera la afectación (≤ %·sueldo)."""
    h = _ingresar(client)
    p = next((x for x in client.get("/api/creditos/portal/productos", headers=h).json() if "Flexible" in x["nombre"]), None)
    if p is None:
        import pytest as _pt; _pt.skip("sin producto")
    sueldo, plazo = 900000, 18
    r = client.post("/api/creditos/portal/pre-aprobado", headers=h,
                    json={"producto_id": p["id"], "plazo": plazo, "sueldo": sueldo, "afectacion_max": 30}).json()
    assert p["monto_min"] <= r["monto_maximo"] <= p["monto_max"]
    assert r["afectacion"] <= 30.5   # la cuota del máximo no supera el margen (±redondeo)
    # Simular ese monto máximo da una cuota que respeta la afectación.
    sim = client.post("/api/creditos/portal/simular", headers=h,
                      json={**CONSENT, "producto_id": p["id"], "monto": r["monto_maximo"], "plazo": plazo, "sueldo": sueldo}).json()
    assert sim["afectacion"] <= 31


def test_haberes_mock_disponible(client):
    """Sin API real configurada, /portal/haberes devuelve el mock (datos demo para autocompletar)."""
    h = _ingresar(client)
    r = client.get("/api/creditos/portal/haberes", headers=h).json()
    assert r["disponible"] is True and r["fuente"] == "mock"
    assert r["sueldo"] and r["antiguedad_meses"] and r["segmento"]


def test_solicitud_registra_fuente_de_haberes(client):
    """La solicitud guarda si los haberes fueron declarados o verificados (Mi Catamarca)."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    body = {**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
            "plazo": min(max(12, p["plazo_min"]), p["plazo_max"]),
            "segmento": "AGENTE_PUBLICO", "fecha_nacimiento": f"{date.today().year - 40}-01-01", "sueldo": 920000, "haberes_fuente": "micatamarca"}
    num = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "hab-1"}, json=body).json()["numero"]
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    back = client.get("/api/creditos/solicitudes", headers={"Authorization": f"Bearer {tok}"}).json()
    match = next(s for s in back["items"] if s["numero"] == num)
    assert match["datosAdicionales"]["haberes_fuente"] == "micatamarca"


def test_simular_con_datos_evalua_elegibilidad_y_afectacion(client):
    """Fase 3: con datos declarados, la simulación devuelve elegibilidad + afectación (cuota/sueldo)."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    monto = min(max(500000.0, p["monto_min"]), p["monto_max"])
    plazo = min(max(12, p["plazo_min"]), p["plazo_max"])
    r = client.post("/api/creditos/portal/simular", headers=h, json={
        **CONSENT, "producto_id": p["id"], "monto": monto, "plazo": plazo,
        "segmento": "AGENTE_PUBLICO", "fecha_nacimiento": f"{date.today().year - 40}-01-01", "antiguedad_meses": 60, "sueldo": 900000}).json()
    assert r["elegible"] in (True, False)          # declaró datos → se evaluó
    assert r["afectacion"] is not None and r["afectacion"] > 0
    # Sin datos → elegible None, afectación None.
    r2 = client.post("/api/creditos/portal/simular", headers=h,
                     json={"producto_id": p["id"], "monto": monto, "plazo": plazo}).json()
    assert r2["elegible"] is None and r2["afectacion"] is None


def test_solicitud_guarda_datos_y_detalle(client):
    """La solicitud guarda los datos declarados; el detalle trae el cronograma y los datos."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    body = {**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
            "plazo": min(max(12, p["plazo_min"]), p["plazo_max"]),
            "segmento": "DOCENTE", "fecha_nacimiento": f"{date.today().year - 35}-01-01", "antiguedad_meses": 24, "sueldo": 800000}
    sol = client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "f3-1"}, json=body).json()
    det = client.get(f"/api/creditos/portal/solicitudes/{sol['numero']}", headers=h).json()
    assert det["segmento"] == "DOCENTE" and det["edad"] == 35 and det["fecha_nacimiento"] == f"{date.today().year - 35}-01-01" and det["antiguedad_meses"] == 24
    assert det["sueldo"] == 800000 and det["afectacion"] is not None
    assert len(det["cuotas"]) == body["plazo"] and det["total_a_pagar"] > 0
    # El backoffice ve el segmento declarado.
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    back = client.get("/api/creditos/solicitudes", headers={"Authorization": f"Bearer {tok}"}).json()
    match = next(s for s in back["items"] if s["numero"] == sol["numero"])
    assert match["segmento"] == "DOCENTE" and match["edad"] == 35


def test_detalle_404_ajeno(client):
    h = _ingresar(client)
    assert client.get("/api/creditos/portal/solicitudes/SOL-9999-99999", headers=h).status_code == 404


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200   # bytes con content-type image/png


def _crear_sol(client, h):
    p = _un_producto(client, h)
    return client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": f"doc-{p['id']}"},
                       json={**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
                             "plazo": min(max(12, p["plazo_min"]), p["plazo_max"])}).json()["numero"]


def test_documento_subir_listar_descargar(client):
    """El ciudadano adjunta un documento a su solicitud; lo lista y lo descarga; el asesor también."""
    h = _ingresar(client)
    numero = _crear_sol(client, h)
    r = client.post(f"/api/creditos/portal/solicitudes/{numero}/documentos", headers=h,
                    files={"archivo": ("dni.png", PNG, "image/png")}, data={"tipo": "DNI_FRENTE"})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["tipo"] == "DNI_FRENTE" and doc["tamano"] == len(PNG)

    lst = client.get(f"/api/creditos/portal/solicitudes/{numero}/documentos", headers=h).json()
    assert lst["puede_subir"] is True and len(lst["items"]) == 1

    dl = client.get(f"/api/creditos/portal/solicitudes/{numero}/documentos/{doc['id']}", headers=h)
    assert dl.status_code == 200 and dl.content == PNG and dl.headers["content-type"].startswith("image/png")

    # El backoffice ve y descarga el documento (por el id de la solicitud).
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    sid = next(s for s in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if s["numero"] == numero)["id"]
    assert len(client.get(f"/api/creditos/solicitudes/{sid}/documentos", headers=hi).json()["items"]) == 1
    assert client.get(f"/api/creditos/solicitudes/{sid}/documentos/{doc['id']}", headers=hi).content == PNG


def test_documento_con_nombre_no_ascii_se_abre(client):
    """Regresión: las capturas de macOS traen un espacio angosto (U+202F) antes de "a. m."; el nombre iba
    tal cual al encabezado Content-Disposition (sólo latin-1) y abrir el documento daba 500, tanto en el
    portal como en la plataforma. Ahora va en UTF-8 (filename*) con un respaldo ASCII."""
    from urllib.parse import quote
    nombre = "Captura de pantalla 2026-09-22 a la(s) 11.46.03\u202fa.\u00a0m. — Peña.png"
    h = _ingresar(client)
    numero = _crear_sol(client, h)
    doc = client.post(f"/api/creditos/portal/solicitudes/{numero}/documentos", headers=h,
                      files={"archivo": (nombre, PNG, "image/png")}, data={"tipo": "DNI_FRENTE"}).json()
    dl = client.get(f"/api/creditos/portal/solicitudes/{numero}/documentos/{doc['id']}", headers=h)
    assert dl.status_code == 200 and dl.content == PNG
    cd = dl.headers["content-disposition"]
    assert cd.startswith("inline; filename=\"Captura de pantalla") and f"filename*=UTF-8''{quote(doc['nombre'], safe='')}" in cd

    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    sid = next(s for s in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if s["numero"] == numero)["id"]
    r = client.get(f"/api/creditos/solicitudes/{sid}/documentos/{doc['id']}", headers=hi)
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"].startswith("image/png")


def _sol_portal_con_docs(client):
    """Solicitud del portal (express) con DNI y recibo adjuntos; devuelve (numero, sid, headers backoffice)."""
    h = _ingresar(client)
    numero = _crear_sol(client, h)
    for nombre, tipo, ct, contenido in (("dni.png", "DNI_FRENTE", "image/png", PNG),
                                        ("recibo.pdf", "RECIBO", "application/pdf", b"%PDF-1.4\n" + b"1" * 100)):
        client.post(f"/api/creditos/portal/solicitudes/{numero}/documentos", headers=h,
                    files={"archivo": (nombre, contenido, ct)}, data={"tipo": tipo})
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    sid = next(s for s in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if s["numero"] == numero)["id"]
    return numero, sid, hi


def _padron_falso(monkeypatch, cliente_id=4321):
    """Módulo Clientes simulado: alta en el padrón, ficha y guardado de documentos (idempotente)."""
    from app.core import clientes_padron
    estado = {"importados": [], "guardados": {}}

    def importar(personas):
        estado["importados"].append(personas)
        return {"creados": {personas[0]["documento"]: cliente_id}, "existentes": {}}

    def copiar(cid, docs):
        ya = estado["guardados"].setdefault(cid, set())
        nuevos = [d for d in docs if d["contenido_base64"] not in ya]
        ya.update(d["contenido_base64"] for d in docs)
        estado.setdefault("lotes", []).append((cid, docs))
        return {"guardados": len(nuevos), "repetidos": len(docs) - len(nuevos)}

    monkeypatch.setattr(clientes_padron, "importar", importar)
    monkeypatch.setattr(clientes_padron, "copiar_documentos", copiar)
    monkeypatch.setattr(clientes_padron, "ficha", lambda cid: {
        "client_id": cid, "nombre": "PEREZ, JUAN CARLOS", "documento": "20301234569", "domicilio": "Sarmiento 100",
        "localidad": "Catamarca", "telefono": "3834000000", "email": "juan@example.com", "cbu": "", "activo": True})
    return estado


def test_crear_cliente_desde_la_solicitud_lleva_datos_y_documentos(client, monkeypatch):
    """El asesor crea el cliente en el módulo Clientes con lo que trajo la solicitud (completando el CUIL y el
    contacto) y los adjuntos del ciudadano quedan guardados en la ficha del cliente."""
    import base64
    estado = _padron_falso(monkeypatch)
    numero, sid, hi = _sol_portal_con_docs(client)
    r = client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={
        "cuil": "20-30123456-9", "telefono": "3834000000", "domicilio": "Sarmiento 100", "localidad": "Catamarca"})
    assert r.status_code == 200, r.text
    assert r.json()["clienteId"] == 4321 and r.json()["documentos"] == {"guardados": 2, "repetidos": 0}
    persona = estado["importados"][0][0]
    assert persona["documento"] == "20301234569" and persona["tipo_documento"] == "CUIL"
    assert persona["apellido"] == "PEREZ" and persona["nombres"] == "JUAN CARLOS"
    assert persona["telefono"] == "3834000000" and persona["localidad"] == "Catamarca"
    assert persona["email"]                     # el mail del ciudadano (Mi Catamarca) viaja solo
    cid, docs = estado["lotes"][0]
    assert cid == 4321 and [d["tipo"] for d in docs] == ["DNI_FRENTE", "RECIBO"]
    assert {d["origen"] for d in docs} == {f"Solicitud {numero}"}
    assert base64.b64decode(docs[0]["contenido_base64"]) == PNG


def test_guardar_documentos_en_el_cliente_es_idempotente(client, monkeypatch):
    estado = _padron_falso(monkeypatch)
    _, sid, hi = _sol_portal_con_docs(client)
    # sin cliente todavía → primero hay que crearlo o vincularlo
    assert client.post(f"/api/creditos/solicitudes/{sid}/documentos/copiar-al-cliente", headers=hi).status_code == 409
    client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={"cuil": "20301234569"})
    r = client.post(f"/api/creditos/solicitudes/{sid}/documentos/copiar-al-cliente", headers=hi)
    assert r.status_code == 200 and r.json() == {"clienteId": 4321, "guardados": 0, "repetidos": 2}
    assert len(estado["lotes"]) == 2


def test_vincular_un_cliente_existente_tambien_guarda_los_documentos(client, monkeypatch):
    estado = _padron_falso(monkeypatch)
    _, sid, hi = _sol_portal_con_docs(client)
    cid = client.get("/api/creditos/clientes", headers=hi).json()["items"][0]["id"]
    r = client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={"cliente_id": cid})
    assert r.status_code == 200 and r.json()["documentos"]["guardados"] == 2
    assert estado["lotes"][0][0] == cid


def test_si_clientes_no_guarda_los_documentos_el_alta_igual_queda(client, monkeypatch):
    """El alta no se deshace porque falle la copia de documentos: se informa y se puede reintentar."""
    from app.core import clientes_padron
    _padron_falso(monkeypatch)

    def cae(_cid, _docs):
        raise clientes_padron.PadronNoDisponible("timeout")

    monkeypatch.setattr(clientes_padron, "copiar_documentos", cae)
    _, sid, hi = _sol_portal_con_docs(client)
    r = client.post(f"/api/creditos/solicitudes/{sid}/promover-cliente", headers=hi, json={"cuil": "20301234569"})
    assert r.status_code == 200 and r.json()["solicitud"]["solicitanteTipo"] == "REGISTRADO"
    assert "No se pudieron copiar" in r.json()["documentos"]["error"]
    assert client.post(f"/api/creditos/solicitudes/{sid}/documentos/copiar-al-cliente", headers=hi).status_code == 503


def test_documento_valida_formato_y_owner(client):
    """Rechaza formatos no permitidos (422) y solicitudes ajenas (404); permite borrar el propio."""
    h = _ingresar(client)
    numero = _crear_sol(client, h)
    bad = client.post(f"/api/creditos/portal/solicitudes/{numero}/documentos", headers=h,
                      files={"archivo": ("virus.exe", b"MZ...", "application/octet-stream")})
    assert bad.status_code == 422
    assert client.post("/api/creditos/portal/solicitudes/SOL-9999-99999/documentos", headers=h,
                       files={"archivo": ("x.png", PNG, "image/png")}).status_code == 404
    doc = client.post(f"/api/creditos/portal/solicitudes/{numero}/documentos", headers=h,
                      files={"archivo": ("recibo.pdf", b"%PDF-1.4 " + b"0" * 50, "application/pdf")},
                      data={"tipo": "RECIBO"}).json()
    assert client.delete(f"/api/creditos/portal/solicitudes/{numero}/documentos/{doc['id']}", headers=h).status_code == 200
    assert len(client.get(f"/api/creditos/portal/solicitudes/{numero}/documentos", headers=h).json()["items"]) == 0


def test_un_solo_documento_de_cada_uno_de_los_pedidos(client):
    """El ciudadano adjunta exactamente un DNI frente, un DNI dorso y un recibo: ni otros tipos, ni un
    segundo del mismo (aunque llame a la API salteando el portal)."""
    h = _ingresar(client)
    numero = _crear_sol(client, h)
    url = f"/api/creditos/portal/solicitudes/{numero}/documentos"
    subir = lambda tipo, nombre="x.png": client.post(url, headers=h, files={"archivo": (nombre, PNG, "image/png")},
                                                      data={"tipo": tipo} if tipo is not None else None)
    for tipo in ("OTRO", "CONSTANCIA", None):          # sin tipo cae en OTRO
        r = subir(tipo)
        assert r.status_code == 422 and "DNI" in r.json()["detail"]
    for tipo in ("DNI_FRENTE", "DNI_DORSO", "SELFIE_DNI", "RECIBO"):
        assert subir(tipo).status_code == 201
    r = subir("DNI_FRENTE", "otra-foto.png")
    assert r.status_code == 409 and "Ya adjuntaste el DNI (frente)" in r.json()["detail"]
    r = subir("SELFIE_DNI", "otra-selfie.png")
    assert r.status_code == 409 and "Ya adjuntaste la selfie con el DNI en la mano" in r.json()["detail"]
    tipos = [d["tipo"] for d in client.get(url, headers=h).json()["items"]]
    assert sorted(tipos) == ["DNI_DORSO", "DNI_FRENTE", "RECIBO", "SELFIE_DNI"]


def test_mis_solicitudes_solo_las_propias(client):
    """'Mis solicitudes' devuelve sólo las del ciudadano autenticado; un token interno no entra."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    client.post("/api/creditos/portal/solicitudes", headers={**h, "Idempotency-Key": "k1"},
                json={**CONSENT, "producto_id": p["id"], "monto": min(max(500000.0, p["monto_min"]), p["monto_max"]),
                      "plazo": min(max(12, p["plazo_min"]), p["plazo_max"])})
    assert client.get("/api/creditos/portal/solicitudes", headers=h).status_code == 200
    # Realm: un token interno no puede usar el endpoint del portal.
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    assert client.get("/api/creditos/portal/solicitudes", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def _bo(client):
    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


def _publicar_con_canales(client, hb, nombre, canales):
    """Crea y publica (backoffice) un producto con Disponibilidad → canales dados."""
    pid = client.post("/api/creditos/productos", headers=hb, json={"nombre": nombre}).json()["id"]
    det = client.get(f"/api/creditos/productos/{pid}", headers=hb).json()
    comps = [{"codigo": c["codigo"], "config": c["config"], "activo": c["activo"], "heredado": c.get("heredado", False)}
             for c in det["componentes"]]
    av = next((c for c in comps if c["codigo"] == "AVAILABILITY"), None)
    if av is None:
        av = {"codigo": "AVAILABILITY", "config": {}, "activo": True, "heredado": False}; comps.append(av)
    av["activo"] = True
    av["config"] = {**(av["config"] or {}), "canales": canales}
    assert client.put(f"/api/creditos/productos/{pid}/config", headers=hb, json={**det["cfg"], "componentes": comps}).status_code == 200
    for acc in ("revisar", "aprobar", "publicar"):
        assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hb, json={"accion": acc}).status_code == 200
    return pid


def test_canal_web_filtra_portal_y_es_configurable(client):
    """H-185: el portal sólo lista/acepta productos habilitados en el canal del portal (Parámetro
    CANAL_PORTAL, configurable). Un producto sólo-SUCURSAL no se ve ni se puede solicitar desde la web;
    cambiar el parámetro cambia qué canal habilita el portal."""
    hb = _bo(client)
    hp = _ingresar(client)
    pid_web = _publicar_con_canales(client, hb, "Solo Web QA", ["WEB"])
    pid_suc = _publicar_con_canales(client, hb, "Solo Sucursal QA", ["SUCURSAL"])

    ids = {p["id"] for p in client.get("/api/creditos/portal/productos", headers=hp).json()}
    assert pid_web in ids            # web-only aparece
    assert pid_suc not in ids        # sucursal-only NO aparece en el portal

    # Guarda dura: aunque conozca el id, no puede solicitar el sucursal-only por la web.
    r = client.post("/api/creditos/portal/solicitudes", headers=hp, json={
        "producto_id": pid_suc, "monto": 500000, "plazo": 12, "apellido": "Perez", "nombre": "Juan",
        "dni": "30123456", "cbu": "2850590940090418135201", "acepta_terminos": True, "acepta_datos": True})
    assert r.status_code == 422 and "canal" in r.text.lower()

    # Configurable: si el canal del portal pasa a SUCURSAL, se invierte qué producto se ofrece.
    assert client.post("/api/creditos/admin/parametros", headers=hb, json={"clave": "CANAL_PORTAL", "valor": "SUCURSAL"}).status_code == 201
    ids2 = {p["id"] for p in client.get("/api/creditos/portal/productos", headers=hp).json()}
    assert pid_suc in ids2 and pid_web not in ids2
    # restaurar
    client.post("/api/creditos/admin/parametros", headers=hb, json={"clave": "CANAL_PORTAL", "valor": "WEB"})


def test_portal_no_muestra_sin_disponibilidad(client):
    """H-189: OPT-IN público — un producto con la Disponibilidad NO configurada (componente inactivo) NO
    aparece en el portal; al activarla con el canal del portal, aparece. Y la disponibilidad se puede
    EDITAR aunque la línea esté publicada (sin crear versión nueva)."""
    hb = _bo(client)
    hp = _ingresar(client)
    # producto publicado SIN disponibilidad (se crea con AVAILABILITY inactiva por defecto)
    pid = client.post("/api/creditos/productos", headers=hb, json={"nombre": "Sin Disp QA"}).json()["id"]
    det = client.get(f"/api/creditos/productos/{pid}", headers=hb).json()
    comps = [{"codigo": c["codigo"], "config": c["config"], "activo": c["activo"], "heredado": c.get("heredado", False)}
             for c in det["componentes"] if c["codigo"] != "AVAILABILITY"]   # sin availability
    client.put(f"/api/creditos/productos/{pid}/config", headers=hb, json={**det["cfg"], "componentes": comps})
    for acc in ("revisar", "aprobar", "publicar"):
        assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hb, json={"accion": acc}).status_code == 200

    ids = {p["id"] for p in client.get("/api/creditos/portal/productos", headers=hp).json()}
    assert pid not in ids   # sin disponibilidad configurada → NO se ofrece por el portal
    # tampoco se puede solicitar
    r = client.post("/api/creditos/portal/solicitudes", headers=hp, json={
        "producto_id": pid, "monto": 500000, "plazo": 12, "apellido": "P", "nombre": "J", "dni": "30123456",
        "cbu": "2850590940090418135201", "acepta_terminos": True, "acepta_datos": True})
    assert r.status_code == 422

    # H-189: editar la disponibilidad de la línea PUBLICADA (activarla con canal WEB) sin versión nueva
    r2 = client.put(f"/api/creditos/productos/{pid}/disponibilidad", headers=hb, json={"activo": True, "canales": ["WEB"]})
    assert r2.status_code == 200
    det2 = client.get(f"/api/creditos/productos/{pid}", headers=hb).json()
    assert det2["estado"] == "PUBLICADO" and det2["disponibilidad"]["canales"] == ["WEB"]
    # ahora sí aparece en el portal
    ids2 = {p["id"] for p in client.get("/api/creditos/portal/productos", headers=hp).json()}
    assert pid in ids2


# ─────────────── Fecha de nacimiento y contacto en la solicitud (H-219) ───────────────

def _enviar(client, h, p, **cambios):
    body = {**CONSENT, "producto_id": p["id"], "monto": 500000.0, "plazo": 12, "segmento": "AGENTE_PUBLICO"}
    body.update(cambios)
    return client.post("/api/creditos/portal/solicitudes", headers=h, json=body)


def test_la_solicitud_pide_fecha_de_nacimiento_y_contacto(client):
    """Ya no se declara la edad: se carga la fecha de nacimiento (y la edad se calcula), más email y
    teléfono para poder avisarle al ciudadano."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    assert _enviar(client, h, p, fecha_nacimiento=None).status_code == 422
    assert "fecha de nacimiento" in _enviar(client, h, p, fecha_nacimiento=None).json()["detail"]
    menor = f"{date.today().year - 15}-01-01"
    assert _enviar(client, h, p, fecha_nacimiento=menor).status_code == 422
    assert _enviar(client, h, p, email="no-es-un-email").status_code == 422
    assert _enviar(client, h, p, telefono="123").status_code == 422

    r = _enviar(client, h, p)
    assert r.status_code == 201, r.text
    numero = r.json()["numero"]
    det = client.get(f"/api/creditos/portal/solicitudes/{numero}", headers=h).json()
    assert det["edad"] == 40 and det["fecha_nacimiento"] == NACIMIENTO_40


def test_el_backoffice_ve_el_nacimiento_el_contacto_y_la_edad_calculada(client):
    """Lo declarado en el portal llega a la ficha del backoffice (y alimenta el alta del cliente)."""
    h = _ingresar(client)
    p = _un_producto(client, h)
    numero = _enviar(client, h, p).json()["numero"]

    tok = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    hi = {"Authorization": f"Bearer {tok}"}
    s = next(x for x in client.get("/api/creditos/solicitudes", headers=hi).json()["items"] if x["numero"] == numero)

    assert s["fechaNacimiento"] == NACIMIENTO_40 and s["edad"] == 40
    assert s["clienteDatos"]["email"] == "juan@example.com"
    assert s["clienteDatos"]["telefono"] == "3834123456"
    assert s["clienteDatos"]["nacimiento"] == NACIMIENTO_40


def test_la_edad_se_calcula_y_no_envejece_sola(client):
    """La edad guardada sale de la fecha: una solicitud vieja no cambia de edad con el tiempo."""
    from app.core.personas import edad_de
    assert edad_de(date(1986, 9, 23), al=date(2026, 9, 22)) == 39     # el día antes del cumpleaños
    assert edad_de(date(1986, 9, 23), al=date(2026, 9, 23)) == 40
    assert edad_de(None) is None

