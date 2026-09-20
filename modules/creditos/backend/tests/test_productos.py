"""Configurar Créditos — catálogo de líneas + workflow de aprobación (Temenos AA)."""
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


ADMIN = ("admin", "admin123")     # ADMG: edita + aprueba
CRED = ("creditos", "cred123")    # XCR: edita
CAJA = ("caja", "caja123")        # XCJ: ninguno


def _activar_wf(objeto: str) -> None:
    """El cuatro-ojos se siembra INACTIVO (app nueva single-admin, H-141); los tests que ejercitan el
    workflow lo activan explícitamente."""
    from app.core.database import SessionLocal
    from app import models_productos as _m
    with SessionLocal() as db:
        r = db.query(_m.PPWorkflowRegla).filter_by(objeto=objeto).first()
        if r:
            r.activo = True; db.commit()


def test_catalogo_sembrado_y_permisos(client):
    h = _auth(client)
    r = client.get("/api/creditos/productos", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    codigos = {p["codigo"] for p in data["items"]}
    assert {"LP-PERS-01", "LP-ADEL-01", "LP-JUB-01", "LP-VIV-01"} <= codigos
    assert data["permisos"] == {"edita": True, "aprueba": True}
    adel = next(p for p in data["items"] if p["codigo"] == "LP-ADEL-01")
    assert adel["estado"] == "EN_REVISION" and adel["enviadoPor"] == "creditos"


def test_permisos_por_perfil(client):
    hc = _auth(client, *CAJA)
    # caja (XCJ) no puede diseñar ni aprobar
    assert client.get("/api/creditos/productos", headers=hc).json()["permisos"] == {"edita": False, "aprueba": False}
    assert client.post("/api/creditos/productos", headers=hc, json={"nombre": "X"}).status_code == 403
    hcred = _auth(client, *CRED)
    assert client.get("/api/creditos/productos", headers=hcred).json()["permisos"] == {"edita": True, "aprueba": False}


def test_workflow_completo_cuatro_ojos(client):
    _activar_wf("LINEA")
    hcred, hadmin = _auth(client, *CRED), _auth(client)
    # créditos diseña y envía a revisión
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Línea WF"}).json()
    pid = p["id"]
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json=p["cfg"])
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    assert r.json()["estado"] == "EN_REVISION" and r.json()["enviadoPor"] == "creditos"
    # créditos NO puede aprobar (perfil)
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "aprobar"}).status_code == 403
    # admin aprueba (distinto usuario) y publica
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert r.status_code == 200 and r.json()["estado"] == "APROBADO" and r.json()["aprobadoPor"] == "admin"
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"})
    assert r.status_code == 200 and r.json()["estado"] == "PUBLICADO" and r.json()["publicadoPor"] == "admin"


def test_aprobar_linea_exige_rol_aun_con_workflow_inactivo(client):
    """H-153: con LINEA sembrada INACTIVA, aprobar una versión EN_REVISION exige rol aprobador. 'caja'
    (XCJ) no puede (403); 'admin' sí. Antes el motor auto-aprobaba sin mirar permisos."""
    hcred, hadmin, hcaja = _auth(client, *CRED), _auth(client), _auth(client, *CAJA)
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Línea gate"}).json()
    pid = p["id"]
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    # workflow inactivo (default): caja no aprueba
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hcaja, json={"accion": "aprobar"}).status_code == 403
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert r.status_code == 200 and r.json()["estado"] == "APROBADO"


def test_cuatro_ojos_bloquea_autoaprobacion(client):
    _activar_wf("LINEA")
    h = _auth(client)  # admin diseña y envía
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Auto"}).json()
    pid = p["id"]
    client.post(f"/api/creditos/productos/{pid}/estado", headers=h, json={"accion": "revisar"})
    # el mismo admin intenta aprobar lo que él envió => 409 separación de funciones
    r = client.post(f"/api/creditos/productos/{pid}/estado", headers=h, json={"accion": "aprobar"})
    assert r.status_code == 409


def test_publicar_requiere_aprobado(client):
    hcred, hadmin = _auth(client, *CRED), _auth(client)
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Pub"}).json()
    pid = p["id"]
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    # publicar directo desde EN_REVISION (sin aprobar) => 409
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"}).status_code == 409


def test_publicar_valida_integridad(client):
    hcred = _auth(client, *CRED)
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Integridad"}).json()
    pid = p["id"]
    # H-099: la validación de integridad es ahora fail-fast al GUARDAR (antes sólo al publicar):
    # ni siquiera se puede persistir una config con montoMin > montoMax.
    bad = client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**p["cfg"], "montoMin": 9e6, "montoMax": 1e6})
    assert bad.status_code == 422  # bloqueo de integridad al guardar


def test_modificar_publicada_es_inmutable_y_nueva_version(client):
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    pid = pers["id"]
    assert client.put(f"/api/creditos/productos/{pid}/config", headers=h, json=pers["cfg"]).status_code == 409
    nv = client.post(f"/api/creditos/productos/{pid}/nueva-version", headers=h).json()
    assert nv["estado"] == "BORRADOR" and nv["derivadaDe"] == pers["version"]
    saved = client.put(f"/api/creditos/productos/{pid}/config", headers=h, json={**nv["cfg"], "tna": 60})
    assert saved.status_code == 200 and saved.json()["cfg"]["tna"] == 60


def test_componentes_config_agregar_quitar(client):
    h = _auth(client)
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Comp"}).json()
    pid = p["id"]
    comps = {c["codigo"]: c for c in p["componentes"]}
    assert comps["ACCOUNTING"]["activo"] is False   # off por defecto
    assert comps["TAX"]["activo"] is True
    # activar ACCOUNTING con su config, editar TAX, y quitar PAYOFF
    nuevos = []
    for c in p["componentes"]:
        if c["codigo"] == "ACCOUNTING":
            nuevos.append({"codigo": c["codigo"], "activo": True, "config": {"cuentaCapital": "9.9.9", "centroCosto": "TEST"}})
        elif c["codigo"] == "TAX":
            nuevos.append({"codigo": c["codigo"], "activo": True, "config": {**c["config"], "ivaInteres": 10.5}})
        elif c["codigo"] == "PAYOFF":
            nuevos.append({"codigo": c["codigo"], "activo": False, "config": c["config"]})
        else:
            nuevos.append({"codigo": c["codigo"], "activo": c["activo"], "config": c["config"]})
    r = client.put(f"/api/creditos/productos/{pid}/config", headers=h, json={**p["cfg"], "componentes": nuevos})
    assert r.status_code == 200
    out = {c["codigo"]: c for c in r.json()["componentes"]}
    assert out["ACCOUNTING"]["activo"] is True and out["ACCOUNTING"]["config"]["centroCosto"] == "TEST"
    assert out["TAX"]["config"]["ivaInteres"] == 10.5
    assert out["PAYOFF"]["activo"] is False


def test_multiples_items_cargos_impuestos(client):
    h = _auth(client)
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Multi"}).json()
    pid = p["id"]
    tax = next(c for c in p["componentes"] if c["codigo"] == "TAX")
    assert isinstance(tax["config"]["items"], list) and len(tax["config"]["items"]) == 3  # default
    nuevos = []
    for c in p["componentes"]:
        if c["codigo"] == "TAX":
            items = [{"etiqueta": "IVA", "base": "INTERES", "porcentaje": 21},
                     {"etiqueta": "Tasa municipal", "base": "CUOTA", "porcentaje": 0.5}]
            nuevos.append({"codigo": c["codigo"], "activo": True, "config": {"items": items}})
        else:
            nuevos.append({"codigo": c["codigo"], "activo": c["activo"], "config": c["config"]})
    r = client.put(f"/api/creditos/productos/{pid}/config", headers=h, json={**p["cfg"], "componentes": nuevos})
    out = next(c for c in r.json()["componentes"] if c["codigo"] == "TAX")
    assert len(out["config"]["items"]) == 2
    assert out["config"]["items"][1]["etiqueta"] == "Tasa municipal"


def test_propiedades_de_interes_nombradas(client):
    h = _auth(client)
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Props"}).json()
    comps = []
    for c in p["componentes"]:
        if c["codigo"] == "INTEREST":
            comps.append({"codigo": "INTEREST", "activo": True, "config": {"items": [
                {"etiqueta": "Compensatorio", "tipo": "COMPENSATORIO", "tna": 52},
                {"etiqueta": "Promocional 3m", "tipo": "PROMOCIONAL", "tna": 30}]}})
        else:
            comps.append({"codigo": c["codigo"], "activo": c["activo"], "config": c["config"]})
    r = client.put(f"/api/creditos/productos/{p['id']}/config", headers=h, json={**p["cfg"], "componentes": comps})
    out = next(c for c in r.json()["componentes"] if c["codigo"] == "INTEREST")
    assert len(out["config"]["items"]) == 2 and out["config"]["items"][1]["tipo"] == "PROMOCIONAL"


def test_copiar_de_clona_configuracion(client):
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    r = client.post("/api/creditos/productos", headers=h, json={"nombre": "Clon", "copiar_de": pers["id"]})
    assert r.status_code == 201
    clon = r.json()
    assert clon["estado"] == "BORRADOR" and clon["version"] == 1
    assert clon["cfg"]["tna"] == pers["cfg"]["tna"] and clon["cfg"]["sistema"] == pers["cfg"]["sistema"]
    # mismos componentes activos
    act_src = {c["codigo"] for c in pers["componentes"] if c["activo"]}
    act_clon = {c["codigo"] for c in clon["componentes"] if c["activo"]}
    assert act_src == act_clon


def test_borrar_solo_borrador_o_revision(client):
    h = _auth(client)
    # crear borrador y borrarlo (línea completa)
    p = client.post("/api/creditos/productos", headers=h, json={"nombre": "Temp"}).json()
    assert client.delete(f"/api/creditos/productos/{p['id']}", headers=h).json()["borro"] == "producto"
    assert client.get(f"/api/creditos/productos/{p['id']}", headers=h).status_code == 404
    # una publicada NO se puede borrar
    pers = next(x for x in client.get("/api/creditos/productos", headers=h).json()["items"] if x["codigo"] == "LP-PERS-01")
    assert client.delete(f"/api/creditos/productos/{pers['id']}", headers=h).status_code == 409
    # nueva versión borrador sobre publicada -> borrar sólo la versión, la línea queda
    nv = client.post(f"/api/creditos/productos/{pers['id']}/nueva-version", headers=h).json()
    assert nv["estado"] == "BORRADOR"
    assert client.delete(f"/api/creditos/productos/{pers['id']}", headers=h).json()["borro"] == "version"
    assert client.get(f"/api/creditos/productos/{pers['id']}", headers=h).json()["estado"] == "PUBLICADO"


def test_versiones_para_comparar(client):
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    pid = pers["id"]
    client.post(f"/api/creditos/productos/{pid}/nueva-version", headers=h)  # crea v(n+1)
    r = client.get(f"/api/creditos/productos/{pid}/versiones", headers=h)
    assert r.status_code == 200
    nums = [v["version"] for v in r.json()["items"]]
    assert nums == sorted(nums) and len(nums) >= 2
    # cada versión trae cfg y componentes para diff
    assert all("cfg" in v and "componentes" in v for v in r.json()["items"])


def test_inspector_modelo_y_raw(client):
    h = _auth(client)
    mod = client.get("/api/creditos/productos/_modelo", headers=h).json()
    tablas = {t["tabla"] for t in mod["tablas"]}
    assert "pp_producto_version" in tablas and "pp_producto_componente" in tablas
    pers = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    raw = client.get(f"/api/creditos/productos/{pers['id']}/raw", headers=h).json()
    assert raw["pp_producto"]["codigo"] == "LP-PERS-01"
    assert raw["versiones"] and raw["versiones"][0]["pp_producto_componente"]


def test_retirar_y_reactivar(client):
    h = _auth(client)
    jub = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-JUB-01")
    pid = jub["id"]
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=h, json={"accion": "retirar"}).json()["estado"] == "RETIRADO"
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=h, json={"accion": "reactivar"}).json()["estado"] == "PUBLICADO"


def test_herencia_deriva_de_padre(client):
    """Fase D: un hijo derivado hereda condiciones del padre; los cambios del padre se propagan."""
    h = _auth(client)
    # Padre editable (borrador) con TNA propia
    padre = client.post("/api/creditos/productos", headers=h, json={"nombre": "Familia Base"}).json()
    ppid = padre["id"]
    client.put(f"/api/creditos/productos/{ppid}/config", headers=h, json={**padre["cfg"], "tna": 55})
    # Hijo derivado: hereda del padre
    hijo = client.post("/api/creditos/productos", headers=h, json={"nombre": "Hija", "padre_id": ppid}).json()
    hid = hijo["id"]
    assert hijo["padre"] and hijo["padre"]["id"] == ppid
    assert hijo["cfgHeredada"] is True
    # Hereda la TNA del padre (55), no la default
    assert hijo["cfg"]["tna"] == 55
    # Cambiar el padre se propaga al hijo mientras siga heredando
    client.put(f"/api/creditos/productos/{ppid}/config", headers=h, json={**padre["cfg"], "tna": 70})
    hijo2 = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["id"] == hid)
    assert hijo2["cfg"]["tna"] == 70
    # El hijo personaliza su TNA: deja de heredar las generales y su valor manda
    client.put(f"/api/creditos/productos/{hid}/config", headers=h, json={**hijo2["cfg"], "tna": 33, "cfgHeredada": False})
    client.put(f"/api/creditos/productos/{ppid}/config", headers=h, json={**padre["cfg"], "tna": 99})
    hijo3 = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["id"] == hid)
    assert hijo3["cfgHeredada"] is False
    assert hijo3["cfg"]["tna"] == 33  # ya no se propaga


def test_simulaciones_persistidas(client):
    """Persistir simulaciones: guardar un escenario con su cronograma, listar y borrar."""
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    pid = pers["id"]
    # Guardar una simulación
    r = client.post(f"/api/creditos/productos/{pid}/simulaciones", headers=h,
                    json={"monto": 1000000, "plazo": 12, "etiqueta": "Escenario base"})
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["etiqueta"] == "Escenario base" and s["plazo"] == 12 and len(s["cuotas"]) == 12
    assert s["totalCuotas"] > 1000000 and s["primeraCuota"] > 0
    # Con tasa negociada (override)
    r2 = client.post(f"/api/creditos/productos/{pid}/simulaciones", headers=h,
                     json={"monto": 1000000, "plazo": 12, "tna": 40, "etiqueta": "Tasa 40"})
    assert r2.json()["tna"] == 40
    # Listar (más reciente primero)
    lst = client.get(f"/api/creditos/productos/{pid}/simulaciones", headers=h).json()
    assert lst["total"] == 2
    # Fuera de rango → 422
    bad = client.post(f"/api/creditos/productos/{pid}/simulaciones", headers=h, json={"monto": 50, "plazo": 12})
    assert bad.status_code == 422
    # Borrar una
    assert client.delete(f"/api/creditos/productos/{pid}/simulaciones/{s['id']}", headers=h).status_code == 200
    assert client.get(f"/api/creditos/productos/{pid}/simulaciones", headers=h).json()["total"] == 1


def test_herencia_usa_version_publicada_no_borrador(client):
    """El hijo hereda de la versión PUBLICADA del padre, no de un borrador nuevo del padre."""
    hcred = _auth(client, "creditos", "cred123")   # diseñador (envía)
    hadmin = _auth(client)                          # aprobador (cuatro-ojos)
    padre = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Padre Pub"}).json()
    pid = padre["id"]
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**padre["cfg"], "tna": 50})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    assert client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"}).json()["estado"] == "PUBLICADO"
    hijo = client.post("/api/creditos/productos", headers=hadmin, json={"nombre": "Hija Pub", "padre_id": pid}).json()
    assert hijo["cfg"]["tna"] == 50
    # El padre abre una NUEVA VERSIÓN en borrador y cambia la TNA a 99 (sin publicar)
    nv = client.post(f"/api/creditos/productos/{pid}/nueva-version", headers=hadmin).json()
    client.put(f"/api/creditos/productos/{pid}/config", headers=hadmin, json={**nv["cfg"], "tna": 99})
    # El hijo debe SEGUIR heredando 50 (la publicada), no 99 (el borrador)
    hijo2 = next(p for p in client.get("/api/creditos/productos", headers=hadmin).json()["items"] if p["id"] == hijo["id"])
    assert hijo2["cfg"]["tna"] == 50


def test_version_vigencia_efectiva_a_futuro(client):
    """Publicar v2 con vigencia futura NO reemplaza a v1 hasta la fecha; v1 se cierra al arrancar v2."""
    import datetime
    hcred = _auth(client, "creditos", "cred123")
    hadmin = _auth(client)
    p = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Vig Test"}).json()
    pid = p["id"]
    # v1: TNA 40, vigencia desde ayer (vigente hoy)
    ayer = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**p["cfg"], "tna": 40, "vigenciaDesde": ayer})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"})
    # v2: TNA 80, vigencia dentro de 30 días (a futuro)
    futuro = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    nv = client.post(f"/api/creditos/productos/{pid}/nueva-version", headers=hadmin).json()
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**nv["cfg"], "tna": 80, "vigenciaDesde": futuro})
    # créditos envía a revisión, admin (distinto) aprueba y publica (cuatro-ojos)
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"})
    # HOY, la oferta/originación debe usar v1 (TNA 40), no v2 (aún no vigente)
    of = next(x for x in client.get("/api/creditos/contratos/oferta", headers=hadmin).json()["items"] if x["id"] == pid)
    assert of["cfg"]["tna"] == 40, f"esperaba v1 (40) vigente hoy, no v2 futura; got {of['cfg']['tna']}"
    # y v1 quedó con vigente_hasta = fecha de v2 (tracking)
    vers = {v["version"]: v for v in client.get(f"/api/creditos/productos/{pid}/versiones", headers=hadmin).json()["items"]}
    assert vers[1]["cfg"]["vigenciaHasta"] == futuro


def test_sistema_calculos_catalogo_y_certificacion(client):
    h = _auth(client)
    r = client.get("/api/creditos/sistema-calculos", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert {s["codigo"] for s in d["sistemas"]} == {"FRANCES", "ALEMAN", "AMERICANO", "BULLET"}
    cert = d["certificacion"]
    assert cert["certificado"] is True and len(cert["checksum"]) == 64  # sha256 hex
    assert cert["reglaRedondeo"] == "HALF_UP"


def test_sistema_calculos_debug_frances_arma_cuotas(client):
    h = _auth(client)
    r = client.post("/api/creditos/sistema-calculos/debug", headers=h,
                    json={"sistema": "FRANCES", "monto": 100000, "plazo": 6, "tna": 52})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["pasos"]) == 6
    # el debug coincide con el motor real (cronograma), y la última cuota cierra en 0
    assert d["pasos"][-1]["saldoFinal"] == "0,00"
    assert d["resumen"]["tna"] == 52.0 and d["resumen"]["tea"] == 66.37
    # cada paso trae el detalle legible (estilo debug)
    assert any("interés = saldo" in l for l in d["pasos"][0]["detalle"])


def test_sistema_calculos_debug_americano_solo_interes(client):
    h = _auth(client)
    d = client.post("/api/creditos/sistema-calculos/debug", headers=h,
                    json={"sistema": "AMERICANO", "monto": 100000, "plazo": 6, "tna": 52}).json()
    # americano: capital 0 salvo la última; interés constante; saldo se mantiene
    assert d["pasos"][0]["capital"] == "0,00"
    assert d["pasos"][0]["saldoInicial"] == d["pasos"][0]["saldoFinal"] == "100.000,00"
    assert d["pasos"][-1]["saldoFinal"] == "0,00"


def test_vencimiento_ajusta_feriado_nacional():
    """El ajuste hábil ahora saltea feriados nacionales fijos, no sólo fines de semana."""
    from datetime import date
    from app.services.productos_calc import cronograma
    # 1er vencimiento cae 2026-01-01 (Año Nuevo, jueves hábil): debe rodar al 02-01.
    f = cronograma("FRANCES", 100000, 3, 52, fecha_valor=date(2025, 12, 2), dia_pago=1,
                   primer_venc_dias=30, ajuste_fin_semana="SIGUIENTE_HABIL")
    assert str(f[0]["fecha_vencimiento"]) == "2026-01-02"
    # Feriado movible inyectado (Carnaval 16-17/02): el vto del 16 rueda al 18.
    f2 = cronograma("FRANCES", 100000, 1, 52, fecha_valor=date(2026, 1, 16), dia_pago=16,
                    primer_venc_dias=31, ajuste_fin_semana="SIGUIENTE_HABIL",
                    feriados={date(2026, 2, 16), date(2026, 2, 17)})
    assert str(f2[0]["fecha_vencimiento"]) == "2026-02-18"
    # SIN_AJUSTE (default) no toca la fecha aunque sea feriado (retrocompatibilidad).
    f3 = cronograma("FRANCES", 100000, 1, 52, fecha_valor=date(2025, 12, 2), dia_pago=1,
                    primer_venc_dias=30)
    assert str(f3[0]["fecha_vencimiento"]) == "2026-01-01"


def test_financiable_tiene_prioridad_sobre_prorrateado():
    """Bug: 'financiable' se ignoraba si el momento era PRORRATEADO. Ahora tiene prioridad."""
    from app.services.productos_calc import cronograma
    scap = lambda f: round(sum(float(x["capital"]) for x in f), 2)
    # financiable=True debe financiar (sumar al capital) sin importar el momento.
    fin_prorr = cronograma("FRANCES", 1_000_000, 12, 50, cargo_pct=5, financiable=True, cargo_momento="PRORRATEADO")
    fin_desem = cronograma("FRANCES", 1_000_000, 12, 50, cargo_pct=5, financiable=True, cargo_momento="DESEMBOLSO")
    assert abs(scap(fin_prorr) - 1_050_000) < 1, "financiable+PRORRATEADO debe financiar (no ignorarse)"
    assert abs(scap(fin_desem) - 1_050_000) < 1
    # Sin financiable: prorrateado reparte en cuotas (capital queda en el monto).
    no_fin = cronograma("FRANCES", 1_000_000, 12, 50, cargo_pct=5, financiable=False, cargo_momento="PRORRATEADO")
    assert abs(scap(no_fin) - 1_000_000) < 1
    assert float(no_fin[0]["cargos"]) > 0  # el cargo aparece prorrateado en la cuota


def test_herencia_usa_version_vigente_no_futura_del_padre(client):
    """El hijo hereda la versión del padre VIGENTE hoy, no una v2 publicada con vigencia futura."""
    import datetime
    hcred = _auth(client, "creditos", "cred123")
    hadmin = _auth(client)
    # Padre: v1 TNA 40, publicada y vigente.
    pa = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Padre Vig"}).json()
    pid = pa["id"]
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**pa["cfg"], "tna": 40})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"})
    # Hijo hereda del padre.
    hijo = client.post("/api/creditos/productos", headers=hcred, json={"nombre": "Hijo Vig", "padre_id": pid}).json()
    hid = hijo["id"]
    assert hijo["cfg"]["tna"] == 40, "hereda la TNA vigente del padre"
    # Padre publica v2 TNA 80 con vigencia a futuro (30 días).
    futuro = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    nv = client.post(f"/api/creditos/productos/{pid}/nueva-version", headers=hadmin).json()
    client.put(f"/api/creditos/productos/{pid}/config", headers=hcred, json={**nv["cfg"], "tna": 80, "vigenciaDesde": futuro})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hcred, json={"accion": "revisar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "aprobar"})
    client.post(f"/api/creditos/productos/{pid}/estado", headers=hadmin, json={"accion": "publicar"})
    # HOY el hijo debe seguir heredando 40 (v1 vigente), no 80 (v2 futura).
    hijo_det = next(x for x in client.get("/api/creditos/productos", headers=hadmin).json()["items"] if x["id"] == hid)
    assert hijo_det["cfg"]["tna"] == 40, f"debe heredar v1 vigente (40), no v2 futura; got {hijo_det['cfg']['tna']}"


def test_simular_preview_no_persiste_y_evalua(client):
    """H-136: el preview de simulación del alta guiada usa el motor único, devuelve cuota + elegibilidad
    y NO persiste una PPSimulacion (no ensucia la lista de simulaciones guardadas del producto)."""
    h = _auth(client)
    pers = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-PERS-01")
    pid = pers["id"]
    antes = client.get(f"/api/creditos/productos/{pid}/simulaciones", headers=h).json()["total"]
    r = client.post(f"/api/creditos/productos/{pid}/simular-preview", headers=h,
                    json={"monto": 500000, "plazo": 12, "segmento": "AGENTE_PUBLICO", "canal": "WEB"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cantidadCuotas"] == 12 and d["cuotaPromedio"] > 0 and d["totalCuotas"] > 0
    assert d["elegible"] is True and isinstance(d["motivos"], list)
    # No elegible cuando el segmento no está habilitado (Jubilados para AGENTE_PUBLICO).
    jub = next(p for p in client.get("/api/creditos/productos", headers=h).json()["items"] if p["codigo"] == "LP-JUB-01")
    d2 = client.post(f"/api/creditos/productos/{jub['id']}/simular-preview", headers=h,
                     json={"monto": 500000, "plazo": 12, "segmento": "AGENTE_PUBLICO", "canal": "SUCURSAL"}).json()
    assert d2["elegible"] is False and d2["motivos"]
    # No persiste: el conteo de simulaciones guardadas no cambió.
    assert client.get(f"/api/creditos/productos/{pid}/simulaciones", headers=h).json()["total"] == antes


def test_duplicar_como_prestamo_independiente(client):
    """H-190: 'Duplicar' crea un préstamo NUEVO e independiente (copia de la config, código propio),
    con trazabilidad copiadoDe; 'publicar-directo' lo publica en un paso (cuatro-ojos inactivo); y se puede
    retirar el original para no ofrecer los dos a la vez."""
    h = _auth(client)
    # préstamo origen, publicado en un paso
    src = client.post("/api/creditos/productos", headers=h, json={"nombre": "Origen"}).json()
    assert client.post(f"/api/creditos/productos/{src['id']}/publicar-directo", headers=h).json()["producto"]["estado"] == "PUBLICADO"

    # duplicar → préstamo nuevo, independiente, borrador, con copiadoDe apuntando al origen
    dup = client.post("/api/creditos/productos", headers=h, json={"copiar_de": src["id"], "nombre": "Origen — copia"}).json()
    assert dup["id"] != src["id"] and dup["codigo"] != src["codigo"] and dup["estado"] == "BORRADOR"
    det = client.get(f"/api/creditos/productos/{dup['id']}", headers=h).json()
    assert det["copiadoDe"] and det["copiadoDe"]["id"] == src["id"] and det["copiadoDe"]["publicado"] is True

    # publicar la copia en un paso
    r = client.post(f"/api/creditos/productos/{dup['id']}/publicar-directo", headers=h).json()
    assert r["needs_approval"] is False and r["producto"]["estado"] == "PUBLICADO"
    # ambos publicados (independientes) hasta que se retire el original
    cat = {p["id"]: p for p in client.get("/api/creditos/productos", headers=h).json()["items"]}
    assert cat[src["id"]]["estado"] == "PUBLICADO" and cat[dup["id"]]["estado"] == "PUBLICADO"

    # retirar el original
    assert client.post(f"/api/creditos/productos/{src['id']}/estado", headers=h, json={"accion": "retirar"}).json()["estado"] == "RETIRADO"
    cat = {p["id"]: p for p in client.get("/api/creditos/productos", headers=h).json()["items"]}
    assert cat[src["id"]]["estado"] == "RETIRADO" and cat[dup["id"]]["estado"] == "PUBLICADO"


def test_decimales_calculo_redondea_la_cuota():
    """H-197: el motor redondea la cuota según `decimales` (Parámetro de créditos DECIMALES_CALCULO)."""
    from app.services.productos_calc import cronograma
    from decimal import Decimal
    f2 = cronograma("FRANCES", 1_000_000, 12, 52, decimales=2)
    f0 = cronograma("FRANCES", 1_000_000, 12, 52, decimales=0)
    # con 2 decimales la cuota tiene centavos; con 0 es entera
    assert f2[0]["total"] == f2[0]["total"].quantize(Decimal("0.01"))
    assert f0[0]["total"] == f0[0]["total"].quantize(Decimal("1"))
    assert f0[0]["total"] == f2[0]["total"].quantize(Decimal("1"))


def test_parametros_por_ambito(client):
    """H-197: los parámetros se filtran por ámbito; los de créditos incluyen DECIMALES_CALCULO."""
    h = _auth(client)
    cred = {p["clave"] for p in client.get("/api/creditos/admin/parametros?ambito=creditos", headers=h).json()}
    assert {"CANALES", "CANAL_PORTAL", "CANAL_BACKOFFICE", "DECIMALES_CALCULO"} <= cred
    conta = {p["clave"] for p in client.get("/api/creditos/admin/parametros?ambito=contabilidad", headers=h).json()}
    assert "CUENTAS_EFECTIVO" in conta and "CANALES" not in conta
