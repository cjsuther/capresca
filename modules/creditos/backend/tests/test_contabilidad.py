"""Contabilidad automática y cierre de caja."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_cont.db"
os.environ["ENVIRONMENT"] = "development"

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _otorgar(client, h, cuotas=3, primer_vto="2026-01-10"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "90000", "cantidad_cuotas": cuotas,
        "fecha_primer_vencimiento": primer_vto,
    }).json()
    return client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()


def _balance(asiento):
    debe = sum(Decimal(l["debe"]) for l in asiento["lineas"])
    haber = sum(Decimal(l["haber"]) for l in asiento["lineas"])
    return debe, haber


def test_plan_cuentas_abm(client):
    """H-172: el Plan de cuentas es editable — se parte de la plantilla base (seed), se pueden crear,
    renombrar/reclasificar y borrar cuentas propias; las base y las que tienen asientos están protegidas."""
    h = _auth(client)
    base = client.get("/api/creditos/contabilidad/plan-cuentas", headers=h).json()
    assert any(c["codigo"] == "1.1.01" and c["base"] for c in base)   # plantilla base presente

    # alta de una cuenta propia
    r = client.post("/api/creditos/contabilidad/plan-cuentas", headers=h, json={"codigo": "1.1.03", "nombre": "Valores a depositar", "tipo": "activo"})
    assert r.status_code == 201 and r.json()["codigo"] == "1.1.03" and r.json()["base"] is False
    cid = r.json()["id"]
    # código duplicado -> 409 ; tipo inválido -> 422
    assert client.post("/api/creditos/contabilidad/plan-cuentas", headers=h, json={"codigo": "1.1.03", "nombre": "X", "tipo": "activo"}).status_code == 409
    assert client.post("/api/creditos/contabilidad/plan-cuentas", headers=h, json={"codigo": "9.9", "nombre": "X", "tipo": "zzz"}).status_code == 422

    # edición (renombra + reclasifica)
    e = client.put(f"/api/creditos/contabilidad/plan-cuentas/{cid}", headers=h, json={"codigo": "1.1.03", "nombre": "Valores al cobro", "tipo": "activo"}).json()
    assert e["nombre"] == "Valores al cobro"
    # no se puede cambiar el código de una cuenta BASE
    base_id = next(c["id"] for c in base if c["codigo"] == "1.1.01")
    assert client.put(f"/api/creditos/contabilidad/plan-cuentas/{base_id}", headers=h, json={"codigo": "1.1.99", "nombre": "Caja", "tipo": "activo"}).status_code == 422
    # no se puede borrar una cuenta BASE
    assert client.delete(f"/api/creditos/contabilidad/plan-cuentas/{base_id}", headers=h).status_code == 422
    # la propia sí se borra
    assert client.delete(f"/api/creditos/contabilidad/plan-cuentas/{cid}", headers=h).status_code == 204

    # restaurar plantilla es idempotente (ya están todas -> 0)
    assert client.post("/api/creditos/contabilidad/plan-cuentas/restaurar-plantilla", headers=h).json()["agregadas"] == 0


def test_plan_cuentas_datos_completos(client):
    """H-174: la cuenta guarda los 'datos de la cuenta' de la pantalla moderna (descripción, alias,
    moneda, tipo/clasificación, saldo normal, imputable, manual y entidades relacionadas)."""
    h = _auth(client)
    r = client.post("/api/creditos/contabilidad/plan-cuentas", headers=h, json={
        "codigo": "1.1.1", "nombre": "Caja y bancos", "tipo": "activo",
        "descripcion": "Disponibilidades", "alias": "CAJABCO", "moneda": "USD",
        "clasificacion": "Banco", "saldo_normal": "acreedor", "imputable": False, "manual": True,
        "entidades": [{"tipo": "Banco", "entidad": "Banco Nación"}, {"tipo": "", "entidad": ""}]})
    assert r.status_code == 201
    c = r.json()
    assert c["descripcion"] == "Disponibilidades" and c["alias"] == "CAJABCO" and c["moneda"] == "USD"
    assert c["clasificacion"] == "Banco" and c["saldo_normal"] == "acreedor"
    assert c["imputable"] is False and c["manual"] is True
    assert c["entidades"] == [{"tipo": "Banco", "entidad": "Banco Nación"}]   # las vacías se descartan
    # persistió (relee)
    det = next(x for x in client.get("/api/creditos/contabilidad/plan-cuentas", headers=h).json() if x["codigo"] == "1.1.1")
    assert det["saldo_normal"] == "acreedor" and det["alias"] == "CAJABCO"


def test_asiento_manual_y_reversa(client):
    """H-176: alta de asiento manual por doble partida (balanceado, cuentas imputables) + reversa
    (contra-asiento con debe/haber invertidos; no borra el original)."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)   # cuentas imputables
    # desbalanceado -> 422
    bad = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "malo", "fecha": "2026-03-01",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 100}, {"cuenta_codigo": "1.1.02", "haber": 90}]})
    assert bad.status_code == 422 and "balanc" in bad.json()["detail"].lower()
    # cuenta de agrupación (no imputable) -> 422
    bad2 = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "grupo", "lineas": [{"cuenta_codigo": "1", "debe": 100}, {"cuenta_codigo": "1.1.02", "haber": 100}]})
    assert bad2.status_code == 422 and "imputable" in bad2.json()["detail"].lower()
    # alta OK, balanceada → nace en BORRADOR
    r = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "Provisión de gastos", "fecha": "2026-03-05", "diario_codigo": "VAR",
        "lineas": [{"cuenta_codigo": "5.1.03", "debe": 15000}, {"cuenta_codigo": "2.1.02", "haber": 15000}]})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["origen"] == "manual" and a["numero"] and a["estado"] == "borrador" and a["diario_codigo"] == "VAR"
    # un borrador NO se reversa: primero se publica
    assert client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/reversar", headers=h).status_code == 422
    pub = client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/publicar", headers=h).json()
    assert pub["estado"] == "publicado"
    # publicado no se puede editar ni eliminar
    assert client.put(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}", headers=h, json={
        "concepto": "x", "lineas": [{"cuenta_codigo": "5.1.03", "debe": 1}, {"cuenta_codigo": "2.1.02", "haber": 1}]}).status_code == 422
    assert client.delete(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}", headers=h).status_code == 422
    # reversa: contra-asiento con debe/haber invertidos y original marcado reversado
    rev = client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/reversar", headers=h).json()
    assert rev["origen"] == "reversa" and rev["reversa_de"] == a["id"]
    lin = {l["cuenta_codigo"]: (float(l["debe"]), float(l["haber"])) for l in rev["lineas"]}
    assert lin["5.1.03"] == (0.0, 15000.0) and lin["2.1.02"] == (15000.0, 0.0)
    # no se puede reversar dos veces
    assert client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/reversar", headers=h).status_code == 422
    # aparece en el listado de manuales (asiento + reversa)
    lst = client.get("/api/creditos/contabilidad/asientos-manuales", headers=h).json()
    assert any(x["id"] == a["id"] for x in lst) and any(x["origen"] == "reversa" for x in lst)


def test_centros_costo_analitica(client):
    """H-182: centros de costo por línea de asiento + reporte por centro. No se admite un centro inexistente."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    centros = client.get("/api/creditos/contabilidad/centros-costo", headers=h).json()   # sembrados
    assert {c["codigo"] for c in centros} >= {"ADM", "COM"}
    # centro inexistente → 422
    bad = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "x", "lineas": [{"cuenta_codigo": "1.1.01", "debe": 100, "centro_codigo": "ZZZ"}, {"cuenta_codigo": "4.1.01", "haber": 100}]})
    assert bad.status_code == 422 and "centro" in bad.json()["detail"].lower()
    # asiento con centro COM en la línea de ingreso, publicado
    a = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "Ingreso comercial", "fecha": "2026-09-01",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 8000, "centro_codigo": "COM"}, {"cuenta_codigo": "4.1.01", "haber": 8000, "centro_codigo": "COM"}]}).json()
    client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/publicar", headers=h)
    pc = client.get("/api/creditos/contabilidad/por-centro", headers=h).json()
    com = next((f for f in pc["filas"] if f["codigo"] == "COM"), None)
    assert com and float(com["debe"]) == 8000 and float(com["haber"]) == 8000
    # la reversa preserva el centro: el contra-asiento cae en el mismo COM (bruto se duplica, neto = 0)
    # y nada cae en "Sin centro".
    client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/reversar", headers=h)
    pc = client.get("/api/creditos/contabilidad/por-centro", headers=h).json()
    com = next((f for f in pc["filas"] if f["codigo"] == "COM"), None)
    assert com and float(com["debe"]) == 16000 and float(com["haber"]) == 16000 and float(com["saldo"]) == 0
    assert not any(f["codigo"] == "" for f in pc["filas"])  # nada cayó en "Sin centro"


def test_e2e_contable(client):
    """Test de punta a punta del circuito contable: plan → parametrización → asiento manual (con centro,
    borrador→publicado) → estados → ejercicio → cierre (resultado + bloqueo)."""
    h = _auth(client)
    # 1) Plan de cuentas estándar
    assert client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h).json()["agregadas"] >= 20
    # 2) Parametrización: el haber del otorgamiento pasa a Banco
    caja = next(i for i in client.get("/api/creditos/contabilidad/imputaciones", headers=h).json() if i["clave"] == "otorgamiento_caja")
    assert client.put(f"/api/creditos/contabilidad/imputaciones/{caja['id']}", headers=h, json={"cuenta_codigo": "1.1.02"}).status_code == 200
    # 3) Asiento manual (aporte de capital) con centro ADM: borrador → no impacta; publicar → impacta
    a = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "Aporte de capital", "fecha": "2026-02-01", "diario_codigo": "CAJA",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 500000, "centro_codigo": "ADM"}, {"cuenta_codigo": "3.1", "haber": 500000, "centro_codigo": "ADM"}]}).json()
    assert a["estado"] == "borrador"
    assert float(client.get("/api/creditos/contabilidad/estados-contables", headers=h).json()["situacion"]["activo"]["total"]) == 0
    client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/publicar", headers=h)
    # un ingreso publicado también
    ing = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "Intereses", "fecha": "2026-03-01",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 40000}, {"cuenta_codigo": "4.1.01", "haber": 40000}]}).json()
    client.post(f"/api/creditos/contabilidad/asientos-manuales/{ing['id']}/publicar", headers=h)
    # 4) Estados: activo/PN reflejan y balancea
    est = client.get("/api/creditos/contabilidad/estados-contables", headers=h).json()
    assert est["situacion"]["balanceado"] is True
    assert float(est["resultados"]["resultado"]) == 40000
    # 5) Ejercicio + cierre: resultado 40.000 y bloqueo del período
    e = client.post("/api/creditos/contabilidad/ejercicios", headers=h, json={"nombre": "2026", "fecha_desde": "2026-01-01", "fecha_hasta": "2026-12-31"}).json()
    cerr = client.post(f"/api/creditos/contabilidad/ejercicios/{e['id']}/cerrar", headers=h).json()
    assert cerr["estado"] == "cerrado" and float(cerr["resultado"]) == 40000
    bloqueado = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "post-cierre", "fecha": "2026-06-01",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 1}, {"cuenta_codigo": "1.1.02", "haber": 1}]})
    assert bloqueado.status_code == 422
    # 6) Export Excel del resultado final
    assert client.get("/api/creditos/contabilidad/estados-contables/excel", headers=h).content[:2] == b"PK"


def test_reportes_excel(client):
    """H-181: export a Excel de los reportes contables (sumas y saldos, estados, libro diario)."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    _asiento_pub(client, h, "Ingreso", [{"cuenta_codigo": "1.1.01", "debe": 5000}, {"cuenta_codigo": "4.1.01", "haber": 5000}], fecha="2026-07-01")
    for url in ("/api/creditos/contabilidad/sumas-y-saldos/excel", "/api/creditos/contabilidad/estados-contables/excel", "/api/creditos/contabilidad/libro-diario/excel"):
        r = client.get(url, headers=h)
        assert r.status_code == 200, url
        assert r.content[:2] == b"PK"   # firma de archivo .xlsx (zip)
        assert "spreadsheetml" in r.headers["content-type"]


def test_ejercicio_cierre_y_bloqueo(client):
    """H-180: cerrar un ejercicio refunde ingresos/egresos en Resultado del ejercicio (3.3) y BLOQUEA la
    carga de asientos en el período; un período cerrado se puede reabrir."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    # un ingreso publicado en 2026: Debe Caja / Haber Intereses ganados 20.000 → ganancia
    _asiento_pub(client, h, "Intereses", [{"cuenta_codigo": "1.1.01", "debe": 20000}, {"cuenta_codigo": "4.1.01", "haber": 20000}], fecha="2026-06-10")
    e = client.post("/api/creditos/contabilidad/ejercicios", headers=h, json={"nombre": "Ejercicio 2026", "fecha_desde": "2026-01-01", "fecha_hasta": "2026-12-31"}).json()
    assert e["estado"] == "abierto"
    # solapamiento rechazado
    assert client.post("/api/creditos/contabilidad/ejercicios", headers=h, json={"nombre": "x", "fecha_desde": "2026-05-01", "fecha_hasta": "2026-07-01"}).status_code == 422
    # cerrar → resultado ganancia 20.000 y se genera el asiento de cierre
    c = client.post(f"/api/creditos/contabilidad/ejercicios/{e['id']}/cerrar", headers=h).json()
    assert c["estado"] == "cerrado" and float(c["resultado"]) == 20000 and c["asiento_cierre_id"]
    # tras el cierre, la cuenta de resultado (4.1.01) quedó en cero en el mayor
    sys = client.get("/api/creditos/contabilidad/sumas-y-saldos", headers=h).json()
    fila_int = next((f for f in sys["filas"] if f["codigo"] == "4.1.01"), None)
    assert fila_int is None or (float(fila_int["saldo_deudor"]) == 0 and float(fila_int["saldo_acreedor"]) == 0)
    # bloqueo: no se puede cargar un asiento con fecha dentro del ejercicio cerrado
    bad = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "en período cerrado", "fecha": "2026-08-01",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 100}, {"cuenta_codigo": "1.1.02", "haber": 100}]})
    assert bad.status_code == 422 and "cerrad" in bad.json()["detail"].lower()
    # reabrir libera el período
    r = client.post(f"/api/creditos/contabilidad/ejercicios/{e['id']}/reabrir", headers=h).json()
    assert r["estado"] == "abierto"
    ok = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "ya reabierto", "fecha": "2026-08-01",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 100}, {"cuenta_codigo": "1.1.02", "haber": 100}]})
    assert ok.status_code == 201


def test_borrador_no_impacta_mayor(client):
    """H-179: un asiento en BORRADOR no mueve el mayor; recién al PUBLICARLO impacta (como Odoo).
    Hay diarios (Caja/Banco/Varios) y el asiento pertenece a uno."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    diarios = client.get("/api/creditos/contabilidad/diarios", headers=h).json()
    assert {d["codigo"] for d in diarios} >= {"CAJA", "BANCO", "VAR"}
    base = float(client.get("/api/creditos/contabilidad/sumas-y-saldos", headers=h).json()["totales"]["debe"])
    a = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": "Ajuste (borrador)", "fecha": "2026-05-01", "diario_codigo": "BANCO",
        "lineas": [{"cuenta_codigo": "1.1.02", "debe": 5000}, {"cuenta_codigo": "4.1.01", "haber": 5000}]}).json()
    assert a["estado"] == "borrador" and a["diario_codigo"] == "BANCO"
    # el borrador NO cambió el mayor
    assert float(client.get("/api/creditos/contabilidad/sumas-y-saldos", headers=h).json()["totales"]["debe"]) == base
    # editar el borrador (cambia importe) sigue sin impactar
    client.put(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}", headers=h, json={
        "concepto": "Ajuste (borrador) v2", "fecha": "2026-05-01", "diario_codigo": "BANCO",
        "lineas": [{"cuenta_codigo": "1.1.02", "debe": 7000}, {"cuenta_codigo": "4.1.01", "haber": 7000}]})
    assert float(client.get("/api/creditos/contabilidad/sumas-y-saldos", headers=h).json()["totales"]["debe"]) == base
    # publicar → ahora sí impacta (+7000 de debe)
    client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/publicar", headers=h)
    assert float(client.get("/api/creditos/contabilidad/sumas-y-saldos", headers=h).json()["totales"]["debe"]) == base + 7000


def test_imputacion_contable_dirige_el_asiento(client):
    """H-178: la parametrización contable (evento → cuenta) manda: si cambio la cuenta del 'haber' del
    otorgamiento, el asiento automático imputa a la cuenta nueva (sin tocar código)."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    ims = client.get("/api/creditos/contabilidad/imputaciones", headers=h).json()
    assert any(i["clave"] == "cobranza_interes" for i in ims)
    caja = next(i for i in ims if i["clave"] == "otorgamiento_caja")
    assert caja["cuenta_codigo"] == "1.1.01"      # default
    # reasigno el haber del otorgamiento a Banco (1.1.02)
    r = client.put(f"/api/creditos/contabilidad/imputaciones/{caja['id']}", headers=h, json={"cuenta_codigo": "1.1.02"})
    assert r.status_code == 200 and r.json()["cuenta_codigo"] == "1.1.02"
    # no se puede mapear a una cuenta de agrupación (no imputable)
    assert client.put(f"/api/creditos/contabilidad/imputaciones/{caja['id']}", headers=h, json={"cuenta_codigo": "1"}).status_code == 422
    # un otorgamiento nuevo imputa el haber a 1.1.02 (Banco)
    cred = _otorgar(client, h)
    diario = client.get("/api/creditos/contabilidad/libro-diario", headers=h).json()
    otorg = next(a for a in diario if a["origen"] == "otorgamiento" and a["ref_id"] == cred["id"])
    haber = [l["cuenta_codigo"] for l in otorg["lineas"] if float(l["haber"]) > 0]
    assert haber == ["1.1.02"]


def _asiento_pub(client, h, concepto, lineas, fecha="2026-04-01"):
    """Crea un asiento manual y lo PUBLICA (recién publicado impacta el mayor)."""
    a = client.post("/api/creditos/contabilidad/asientos-manuales", headers=h, json={
        "concepto": concepto, "fecha": fecha, "lineas": lineas}).json()
    client.post(f"/api/creditos/contabilidad/asientos-manuales/{a['id']}/publicar", headers=h)
    return a


def test_estados_contables(client):
    """H-177: sumas y saldos + estados contables desde los asientos PUBLICADOS. Un asiento (Debe Muebles /
    Haber Proveedores) refleja Activo=Pasivo y balancea; un ingreso da resultado (ganancia)."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    # compra de bienes de uso a crédito: Debe 1.4.01 (activo) / Haber 2.1.02 (pasivo) por 80.000
    _asiento_pub(client, h, "Compra de muebles a crédito",
                 [{"cuenta_codigo": "1.4.01", "debe": 80000}, {"cuenta_codigo": "2.1.02", "haber": 80000}])
    # sumas y saldos balancea
    sys = client.get("/api/creditos/contabilidad/sumas-y-saldos", headers=h).json()
    assert sys["balanceado"] is True and float(sys["totales"]["debe"]) >= 80000
    # estados: activo y pasivo suben 80.000 y la situación balancea
    est = client.get("/api/creditos/contabilidad/estados-contables", headers=h).json()
    sit = est["situacion"]
    assert float(sit["activo"]["total"]) >= 80000 and float(sit["pasivo"]["total"]) >= 80000
    assert sit["balanceado"] is True
    # un ingreso: Debe Caja / Haber Intereses ganados → resultado ganancia
    _asiento_pub(client, h, "Intereses cobrados",
                 [{"cuenta_codigo": "1.1.01", "debe": 12000}, {"cuenta_codigo": "4.1.01", "haber": 12000}], fecha="2026-04-02")
    est2 = client.get("/api/creditos/contabilidad/estados-contables", headers=h).json()
    assert float(est2["resultados"]["ingresos"]["total"]) >= 12000
    assert float(est2["resultados"]["resultado"]) >= 12000 and est2["situacion"]["balanceado"] is True


def test_cargar_plan_estandar(client):
    """H-175: 'Cargar plan estándar' puebla el árbol con un chart completo (Activo/Pasivo/PN/Ingresos/
    Egresos + subcuentas), idempotente; los grupos quedan no imputables y con saldo normal por rubro."""
    h = _auth(client)
    r = client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h).json()
    assert r["agregadas"] > 20
    cuentas = client.get("/api/creditos/contabilidad/plan-cuentas", headers=h).json()
    by = {c["codigo"]: c for c in cuentas}
    assert by["1"]["nombre"] == "Activo" and by["1"]["imputable"] is False        # grupo raíz
    assert by["5"]["tipo"] == "egreso" and by["5.1.01"]["imputable"] is True       # egresos + hoja
    assert by["2.1.02"]["nombre"] == "Proveedores" and by["2.1.02"]["saldo_normal"] == "acreedor"
    assert by["1.1.01"]["saldo_normal"] == "deudor"
    # idempotente: segunda carga no agrega nada
    assert client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h).json()["agregadas"] == 0


def test_plan_cuentas_refleja_nombre_en_asientos(client):
    """H-172: renombrar una cuenta base se refleja en los asientos NUEVOS (nombre resuelto del plan)."""
    h = _auth(client)
    cuentas = client.get("/api/creditos/contabilidad/plan-cuentas", headers=h).json()
    caja = next(c for c in cuentas if c["codigo"] == "1.1.01")
    client.put(f"/api/creditos/contabilidad/plan-cuentas/{caja['id']}", headers=h, json={"codigo": "1.1.01", "nombre": "Caja general", "tipo": "activo"})
    cred = _otorgar(client, h)
    diario = client.get("/api/creditos/contabilidad/libro-diario", headers=h).json()
    otorg = next(a for a in diario if a["origen"] == "otorgamiento" and a["ref_id"] == cred["id"])
    linea_caja = next(l for l in otorg["lineas"] if l["cuenta_codigo"] == "1.1.01")
    assert linea_caja["cuenta_nombre"] == "Caja general"


def test_asiento_otorgamiento_balanceado(client):
    h = _auth(client)
    cred = _otorgar(client, h)
    diario = client.get("/api/creditos/contabilidad/libro-diario", headers=h).json()
    otorg = [a for a in diario if a["origen"] == "otorgamiento" and a["ref_id"] == cred["id"]]
    assert len(otorg) == 1
    debe, haber = _balance(otorg[0])
    assert debe == haber == Decimal("90000.00")
    # créditos a cobrar al debe, caja al haber
    codigos = {l["cuenta_codigo"] for l in otorg[0]["lineas"]}
    assert "1.2.01" in codigos and "1.1.01" in codigos


def test_asiento_cobranza_balanceado(client):
    h = _auth(client)
    cred = _otorgar(client, h)
    r = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1], "fecha_pago": "2026-01-10",
    }).json()
    diario = client.get("/api/creditos/contabilidad/libro-diario", headers=h).json()
    cob = [a for a in diario if a["origen"] == "cobranza" and a["ref_id"] == r["id"]]
    assert len(cob) == 1
    debe, haber = _balance(cob[0])
    assert debe == haber
    assert debe == Decimal(str(r["total"]))  # debe (caja) = total del recibo


def test_cierre_de_caja(client):
    h = _auth(client)
    cred = _otorgar(client, h)
    # fecha de cobro única para aislar el cierre de otros tests que comparten DB
    fecha = "2026-06-01"
    client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cred["id"], "cuotas": [1, 2], "fecha_pago": fecha,
    })
    cierre = client.get(f"/api/creditos/caja/cierre?fecha={fecha}", headers=h).json()
    assert cierre["cantidad_recibos"] == 1
    assert Decimal(cierre["total_cobrado"]) > 0
    conceptos = {c["concepto"] for c in cierre["por_concepto"]}
    assert "Capital" in conceptos and "Interés" in conceptos


def teardown_module(_):
    if os.path.exists("_cont.db"):
        os.remove("_cont.db")


def test_balance_sumas_saldos_cuadra(client):
    h = _auth(client)
    _otorgar(client, h)  # genera asiento de otorgamiento
    b = client.get("/api/creditos/contabilidad/balance", headers=h).json()
    assert b["cuentas"], "debe haber cuentas con movimiento"
    # sumas iguales y saldos iguales -> cuadra
    assert Decimal(b["total"]["debe"]) == Decimal(b["total"]["haber"])
    assert Decimal(b["total"]["deudor"]) == Decimal(b["total"]["acreedor"])
    assert b["cuadra"] is True
    # PDF
    pdf = client.get("/api/creditos/contabilidad/balance/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_balance_y_mayor_real(client):
    """Balance y mayor sobre el libro mayor real (movimientos_contables)."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.MovimientoContable(cuenta="PPS/DE", periodo="202405",
        fecha=datetime.date(2024, 5, 17), norden=1, debito=Decimal("1000"), credito=Decimal("0")))
    db.add(models.MovimientoContable(cuenta="PPS/DE", periodo="202405",
        fecha=datetime.date(2024, 5, 18), norden=2, debito=Decimal("0"), credito=Decimal("300")))
    db.add(models.MovimientoContable(cuenta="PPC/DE", periodo="202405",
        fecha=datetime.date(2024, 5, 18), norden=3, debito=Decimal("500"), credito=Decimal("0")))
    db.commit(); db.close()

    bal = client.get("/api/creditos/contabilidad/mayor/balance?periodo=202405", headers=h).json()
    ppsde = next(c for c in bal["cuentas"] if c["cuenta"] == "PPS/DE")
    assert Decimal(ppsde["debito"]) == Decimal("1000.00")
    assert Decimal(ppsde["credito"]) == Decimal("300.00")
    assert Decimal(ppsde["saldo_deudor"]) == Decimal("700.00")   # 1000 - 300
    assert Decimal(bal["total_debito"]) == Decimal("1500.00")

    may = client.get("/api/creditos/contabilidad/mayor/cuenta?cuenta=PPS/DE", headers=h).json()
    assert may["total"] == 2 and Decimal(may["saldo"]) == Decimal("700.00")


def test_iva_cuotas_cobradas_real(client):
    """IVA de cuotas cobradas por período sobre dato real (maecuotas)."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    cli_id = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    db = SessionLocal()
    # crédito + cuota pagada con IVA
    cr = models.Credito(cliente_id=cli_id, capital=Decimal("1000"),
                        saldo_capital=Decimal("0"), estado="A")
    db.add(cr); db.flush()
    db.add(models.Cuota(credito_id=cr.id, numero=1, fecha_vencimiento=datetime.date(2025, 3, 10),
        saldo_capital=Decimal("0"), amortizacion=Decimal("100"), interes=Decimal("50"),
        iva_interes=Decimal("10.50"), seguro=Decimal("0"), iva_seguro=Decimal("0"),
        gastos_adm=Decimal("0"), iva_gastos_adm=Decimal("2.00"), total=Decimal("162.50"),
        total_pagado=Decimal("162.50"), estado="P", fecha_pago=datetime.date(2025, 3, 15)))
    db.commit(); db.close()

    d = client.get("/api/creditos/contabilidad/iva-cuotas?desde=2025-03-01&hasta=2025-03-31", headers=h).json()
    assert Decimal(d["total_iva"]) == Decimal("12.50")   # 10.50 + 2.00
    p = next(x for x in d["periodos"] if x["periodo"] == "202503")
    assert Decimal(p["iva_interes"]) == Decimal("10.50") and Decimal(p["iva_gastos"]) == Decimal("2.00")


def test_flujo_efectivo(client):
    """H-186: flujo de efectivo (método directo) — saldo inicial + entradas/salidas por contrapartida +
    saldo final, sobre las cuentas de efectivo (Caja/Banco)."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    # Enero: aporte a Caja (entrada de 100.000 desde Capital 3.1)
    _asiento_pub(client, h, "Aporte", [{"cuenta_codigo": "1.1.01", "debe": 100000},
                                        {"cuenta_codigo": "3.1", "haber": 100000}], fecha="2026-01-15")
    # Febrero: pago de gastos (salida de 30.000 hacia 4.1.04)
    _asiento_pub(client, h, "Gastos", [{"cuenta_codigo": "4.1.04", "debe": 30000},
                                        {"cuenta_codigo": "1.1.01", "haber": 30000}], fecha="2026-02-10")

    # Período completo: entrada 100k, salida 30k, neto 70k
    f = client.get("/api/creditos/contabilidad/flujo-efectivo", headers=h).json()
    assert Decimal(f["total_entradas"]) == Decimal("100000")
    assert Decimal(f["total_salidas"]) == Decimal("30000")
    assert Decimal(f["neto"]) == Decimal("70000") and Decimal(f["saldo_final"]) == Decimal("70000")
    ent = {x["codigo"]: Decimal(x["monto"]) for x in f["entradas"]}
    sal = {x["codigo"]: Decimal(x["monto"]) for x in f["salidas"]}
    assert ent["3.1"] == Decimal("100000") and sal["4.1.04"] == Decimal("30000")

    # Desde febrero: saldo inicial arrastra los 100k de enero; en el período sólo la salida de 30k
    f2 = client.get("/api/creditos/contabilidad/flujo-efectivo?desde=2026-02-01", headers=h).json()
    assert Decimal(f2["saldo_inicial"]) == Decimal("100000")
    assert Decimal(f2["total_entradas"]) == Decimal("0") and Decimal(f2["total_salidas"]) == Decimal("30000")
    assert Decimal(f2["neto"]) == Decimal("-30000") and Decimal(f2["saldo_final"]) == Decimal("70000")


def test_conciliacion_bancaria(client):
    """H-187: conciliación bancaria — extracto vs mayor de la cuenta banco, conciliar manual + automático,
    validación de importe, y diferencia de saldos."""
    h = _auth(client)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)
    B = "1.1.02"
    # dos movimientos en Banco: depósito 50.000 (debe) y pago 20.000 (haber)
    _asiento_pub(client, h, "Depósito", [{"cuenta_codigo": B, "debe": 50000}, {"cuenta_codigo": "3.1", "haber": 50000}], fecha="2026-03-01")
    _asiento_pub(client, h, "Pago prov", [{"cuenta_codigo": "5.1.03", "debe": 20000}, {"cuenta_codigo": B, "haber": 20000}], fecha="2026-03-05")

    # extracto: +50.000 y −20.000
    e1 = client.post("/api/creditos/contabilidad/conciliacion/extracto", headers=h, json={"cuenta_codigo": B, "fecha": "2026-03-01", "descripcion": "Dep", "importe": 50000}).json()["id"]
    e2 = client.post("/api/creditos/contabilidad/conciliacion/extracto", headers=h, json={"cuenta_codigo": B, "fecha": "2026-03-06", "descripcion": "Pago", "importe": -20000}).json()["id"]

    est = client.get(f"/api/creditos/contabilidad/conciliacion?cuenta={B}", headers=h).json()
    assert Decimal(est["saldo_extracto"]) == Decimal("30000") and Decimal(est["saldo_mayor"]) == Decimal("30000")
    assert Decimal(est["diferencia"]) == Decimal("0")
    assert est["pendientes_extracto"] == 2 and est["pendientes_mayor"] == 2
    may = {Decimal(m["importe"]): m["asiento_linea_id"] for m in est["mayor"]}

    # conciliar manual el depósito; importe que no coincide → 422
    assert client.post("/api/creditos/contabilidad/conciliacion/conciliar", headers=h, json={"extracto_id": e2, "asiento_linea_id": may[Decimal("50000")]}).status_code == 422
    ok = client.post("/api/creditos/contabilidad/conciliacion/conciliar", headers=h, json={"extracto_id": e1, "asiento_linea_id": may[Decimal("50000")]})
    assert ok.status_code == 200 and ok.json()["conciliada"] is True

    # automática concilia el par restante (−20.000)
    aut = client.post(f"/api/creditos/contabilidad/conciliacion/automatica?cuenta={B}", headers=h).json()
    assert aut["conciliadas"] == 1
    est2 = client.get(f"/api/creditos/contabilidad/conciliacion?cuenta={B}", headers=h).json()
    assert est2["pendientes_extracto"] == 0 and est2["pendientes_mayor"] == 0

    # desconciliar deja el par pendiente otra vez
    client.post(f"/api/creditos/contabilidad/conciliacion/desconciliar/{e1}", headers=h)
    assert client.get(f"/api/creditos/contabilidad/conciliacion?cuenta={B}", headers=h).json()["pendientes_extracto"] == 1


def test_libros_separados_por_empresa(client):
    """H-188: contabilidad por EMPRESA — cada empresa tiene su plan y sus libros. Un asiento de la empresa
    B no aparece en los reportes de la empresa A (predeterminada), y los códigos de cuenta pueden repetirse
    entre empresas."""
    h = _auth(client)
    # empresa predeterminada (A)
    emps = client.get("/api/creditos/contabilidad/empresas", headers=h).json()
    a = next(e for e in emps if e["predeterminada"])
    # crear empresa B
    b = client.post("/api/creditos/contabilidad/empresas", headers=h, json={"codigo": "B", "nombre": "Empresa B"}).json()
    bid = b["id"]
    assert bid != a["id"]

    # plan estándar en A y en B (códigos iguales conviven porque el código es único POR empresa)
    client.post("/api/creditos/contabilidad/plan-cuentas/cargar-estandar", headers=h)                       # A (default)
    assert client.post(f"/api/creditos/contabilidad/plan-cuentas/cargar-estandar?empresa_id={bid}", headers=h).json()["agregadas"] >= 20
    codes_a = {c["codigo"] for c in client.get("/api/creditos/contabilidad/plan-cuentas", headers=h).json()}
    codes_b = {c["codigo"] for c in client.get(f"/api/creditos/contabilidad/plan-cuentas?empresa_id={bid}", headers=h).json()}
    assert "1.1.01" in codes_a and "1.1.01" in codes_b   # mismo código en ambas empresas

    # asiento en la empresa B, publicado
    ab = client.post(f"/api/creditos/contabilidad/asientos-manuales?empresa_id={bid}", headers=h, json={
        "concepto": "Aporte B", "fecha": "2026-04-01",
        "lineas": [{"cuenta_codigo": "1.1.01", "debe": 77000}, {"cuenta_codigo": "3.1", "haber": 77000}]}).json()
    assert ab["estado"] == "borrador"
    client.post(f"/api/creditos/contabilidad/asientos-manuales/{ab['id']}/publicar", headers=h)

    # sumas y saldos de B lo ve; las de A (default) NO
    sy_b = client.get(f"/api/creditos/contabilidad/sumas-y-saldos?empresa_id={bid}", headers=h).json()
    sy_a = client.get("/api/creditos/contabilidad/sumas-y-saldos", headers=h).json()
    caja_b = next((f for f in sy_b["filas"] if f["codigo"] == "1.1.01"), None)
    caja_a = next((f for f in sy_a["filas"] if f["codigo"] == "1.1.01"), None)
    assert caja_b and Decimal(caja_b["debe"]) == Decimal("77000")
    assert caja_a is None or Decimal(caja_a["debe"]) == Decimal("0")   # A no ve el asiento de B
    # el asiento de B aparece en asientos-manuales de B, no en los de A
    assert any(x["id"] == ab["id"] for x in client.get(f"/api/creditos/contabilidad/asientos-manuales?empresa_id={bid}", headers=h).json())
    assert not any(x["id"] == ab["id"] for x in client.get("/api/creditos/contabilidad/asientos-manuales", headers=h).json())
