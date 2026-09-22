"""Lo que además tiene que tener el módulo: entes, borradores, apertura/reapertura, conciliación
bancaria, flujo de efectivo, posición de IVA y análisis por centro de costo."""
from datetime import date, timedelta

from app import models

API = "/api/contabilidad"
HOY = date.today().isoformat()
ANIO = date.today().year


def _asiento(client, contador, *, debe="1.1.01", haber="1.1.02", importe=1000.0, concepto="Ajuste",
             fecha=None, borrador=False, centro=""):
    return client.post(f"{API}/asientos", headers=contador, json={
        "fecha": fecha or HOY, "concepto": concepto, "borrador": borrador,
        "lineas": [{"cuenta": debe, "debe": importe, "centro": centro},
                   {"cuenta": haber, "haber": importe, "centro": centro}]})


# ── Ente contable ────────────────────────────────────────────────────────────────────────────────

def test_el_ente_contable_guarda_cuit_y_condicion_frente_al_iva(client, contador):
    assert client.get(f"{API}/empresas", headers=contador).json()["total"] == 1
    r = client.post(f"{API}/empresas", headers=contador, json={
        "razon_social": "Capresca SE", "cuit": "30-71234567-8", "condicion_iva": "RESPONSABLE_INSCRIPTO",
        "domicilio": "San Martín 100"})
    assert r.status_code == 201 and r.json()["cuit"] == "30712345678"
    e = r.json()
    assert client.put(f"{API}/empresas/{e['id']}", headers=contador,
                      json={"razon_social": "Capresca S.E.", "cuit": "30712345678"}).json()["razonSocial"] == "Capresca S.E."


# ── Plan de cuentas: baja y borrado ──────────────────────────────────────────────────────────────

def test_una_cuenta_sin_uso_se_borra_y_una_con_movimientos_no(client, contador, db):
    nueva = client.post(f"{API}/cuentas", headers=contador, json={
        "codigo": "9.9.99", "nombre": "Cuenta de prueba", "rubro": "ACTIVO"}).json()
    assert client.delete(f"{API}/cuentas/{nueva['id']}", headers=contador).status_code == 204

    _asiento(client, contador)
    caja = db.query(models.Cuenta).filter_by(codigo="1.1.01").one()
    r = client.delete(f"{API}/cuentas/{caja.id}", headers=contador)
    assert r.status_code == 409 and "movimiento" in r.json()["detail"]


def test_no_se_borra_una_cuenta_que_usa_una_definicion(client, contador):
    nueva = client.post(f"{API}/cuentas", headers=contador, json={
        "codigo": "9.9.98", "nombre": "Usada", "rubro": "ACTIVO"}).json()
    client.post(f"{API}/definiciones", headers=contador, json={
        "modulo": "x", "tipo": "Y", "nombre": "Prueba",
        "lineas": [{"cuenta": "9.9.98", "dc": "DEBE", "importe": "monto"},
                   {"cuenta": "1.1.02", "dc": "HABER", "importe": "monto"}]})
    r = client.delete(f"{API}/cuentas/{nueva['id']}", headers=contador)
    assert r.status_code == 409 and "definición" in r.json()["detail"]


# ── Asientos en borrador ─────────────────────────────────────────────────────────────────────────

def test_un_borrador_no_entra_en_los_libros_hasta_publicarlo(client, contador):
    b = _asiento(client, contador, borrador=True, concepto="En revisión").json()
    assert b["estado"] == "BORRADOR"
    assert client.get(f"{API}/libros/sumas-y-saldos", headers=contador).json()["totales"]["debe"] == 0.0

    r = client.post(f"{API}/asientos/{b['id']}/publicar", headers=contador).json()
    assert r["estado"] == "REGISTRADO"
    assert client.get(f"{API}/libros/sumas-y-saldos", headers=contador).json()["totales"]["debe"] == 1000.0


def test_un_borrador_se_borra_y_un_registrado_no(client, contador):
    b = _asiento(client, contador, borrador=True).json()
    assert client.delete(f"{API}/asientos/{b['id']}", headers=contador).status_code == 204
    a = _asiento(client, contador).json()
    r = client.delete(f"{API}/asientos/{a['id']}", headers=contador)
    assert r.status_code == 409 and "anula" in r.json()["detail"]


# ── Apertura y reapertura de ejercicio ───────────────────────────────────────────────────────────

def _ejercicio_siguiente(client, contador):
    return client.post(f"{API}/ejercicios", headers=contador, json={
        "numero": ANIO + 1, "desde": f"{ANIO + 1}-01-01", "hasta": f"{ANIO + 1}-12-31",
        "cuenta_resultado": "3.3"}).json()


def test_el_ejercicio_nuevo_abre_con_los_saldos_patrimoniales_del_anterior(client, contador):
    _asiento(client, contador, debe="1.1.01", haber="3.1", importe=50000)   # aporte de capital
    ej_actual = client.get(f"{API}/ejercicios", headers=contador).json()["items"][0]
    client.post(f"{API}/ejercicios/{ej_actual['id']}/cerrar", headers=contador)
    nuevo = _ejercicio_siguiente(client, contador)

    a = client.post(f"{API}/ejercicios/{nuevo['id']}/apertura", headers=contador).json()

    assert a["origen"] == "APERTURA" and a["debe"] == a["haber"] == 50000.0
    assert {l["cuenta"] for l in a["lineas"]} == {"1.1.01", "3.1"}
    # No se abre dos veces.
    assert client.post(f"{API}/ejercicios/{nuevo['id']}/apertura", headers=contador).status_code == 422


def test_sin_ejercicio_anterior_no_hay_apertura(client, contador):
    nuevo = _ejercicio_siguiente(client, contador)
    # el ejercicio anterior existe pero no dejó saldos
    r = client.post(f"{API}/ejercicios/{nuevo['id']}/apertura", headers=contador)
    assert r.status_code == 422 and "saldos" in r.json()["detail"]


def test_reabrir_un_ejercicio_anula_su_asiento_de_cierre(client, contador):
    _asiento(client, contador, debe="1.1.01", haber="4.1.04", importe=7000)
    ej = client.get(f"{API}/ejercicios", headers=contador).json()["items"][0]
    client.post(f"{API}/ejercicios/{ej['id']}/cerrar", headers=contador)

    r = client.post(f"{API}/ejercicios/{ej['id']}/reabrir", headers=contador).json()

    assert r["estado"] == "ABIERTO" and r["cierreAnulado"] and r["contraAsiento"]
    assert _asiento(client, contador).status_code == 201        # vuelve a admitir asientos
    estados = client.get(f"{API}/libros/estados", headers=contador).json()
    assert estados["resultados"]["resultado"] == 7000.0          # los resultados volvieron
    assert client.post(f"{API}/ejercicios/{ej['id']}/reabrir", headers=contador).status_code == 422


# ── Conciliación bancaria ────────────────────────────────────────────────────────────────────────

def _extracto(client, contador, importe, fecha=None, descripcion="Transferencia"):
    return client.post(f"{API}/conciliacion/extracto", headers=contador, json={
        "cuenta_codigo": "1.1.02", "fecha": fecha or HOY, "importe": importe,
        "descripcion": descripcion}).json()


def test_la_conciliacion_muestra_las_dos_columnas_y_la_diferencia(client, contador):
    _asiento(client, contador, debe="1.1.02", haber="4.1.04", importe=3000)   # entra plata al banco
    _extracto(client, contador, 3000)
    _extracto(client, contador, -500, descripcion="Gastos bancarios no registrados")

    d = client.get(f"{API}/conciliacion?cuenta=1.1.02", headers=contador).json()

    assert d["totales"]["saldoExtracto"] == 2500.0 and d["totales"]["saldoMayor"] == 3000.0
    assert d["totales"]["diferencia"] == -500.0
    assert len(d["extracto"]) == 2 and len(d["movimientos"]) == 1


def test_conciliar_exige_que_los_importes_coincidan(client, contador):
    _asiento(client, contador, debe="1.1.02", haber="4.1.04", importe=3000)
    e = _extracto(client, contador, 2500)
    d = client.get(f"{API}/conciliacion?cuenta=1.1.02", headers=contador).json()
    mov = d["movimientos"][0]["asientoLineaId"]
    r = client.post(f"{API}/conciliacion/conciliar", headers=contador,
                    json={"extracto_id": e["id"], "asiento_linea_id": mov})
    assert r.status_code == 422 and "no coinciden" in r.json()["detail"]


def test_conciliar_y_desconciliar_a_mano(client, contador):
    _asiento(client, contador, debe="1.1.02", haber="4.1.04", importe=3000)
    e = _extracto(client, contador, 3000)
    d = client.get(f"{API}/conciliacion?cuenta=1.1.02", headers=contador).json()
    mov = d["movimientos"][0]["asientoLineaId"]

    assert client.post(f"{API}/conciliacion/conciliar", headers=contador,
                       json={"extracto_id": e["id"], "asiento_linea_id": mov}).json()["conciliada"] is True
    d = client.get(f"{API}/conciliacion?cuenta=1.1.02", headers=contador).json()
    assert d["extracto"][0]["conciliada"] and d["movimientos"][0]["conciliada"]
    assert d["totales"]["pendienteExtracto"] == 0.0

    # el mismo movimiento no se concilia dos veces
    otra = _extracto(client, contador, 3000)
    r = client.post(f"{API}/conciliacion/conciliar", headers=contador,
                    json={"extracto_id": otra["id"], "asiento_linea_id": mov})
    assert r.status_code == 422 and "ya está conciliado" in r.json()["detail"]

    client.post(f"{API}/conciliacion/desconciliar/{e['id']}", headers=contador)
    assert client.get(f"{API}/conciliacion?cuenta=1.1.02", headers=contador).json()["extracto"][0]["conciliada"] is False


def test_la_conciliacion_automatica_empareja_por_importe_y_fecha(client, contador):
    ayer = (date.today() - timedelta(days=1)).isoformat()
    _asiento(client, contador, debe="1.1.02", haber="4.1.04", importe=1200)
    _asiento(client, contador, debe="1.1.02", haber="4.1.04", importe=800, fecha=ayer)
    _asiento(client, contador, debe="1.1.02", haber="4.1.04", importe=999)      # sin par en el extracto
    _extracto(client, contador, 1200)
    _extracto(client, contador, 800, fecha=ayer)

    r = client.post(f"{API}/conciliacion/automatica?cuenta=1.1.02", headers=contador).json()

    assert r["conciliadas"] == 2 and r["pendienteExtracto"] == 0.0
    assert r["pendienteMayor"] == 999.0
    assert client.delete(f"{API}/conciliacion/extracto/999", headers=contador).status_code == 404


# ── Flujo de efectivo, IVA y centros ─────────────────────────────────────────────────────────────

def test_flujo_de_efectivo_por_caja_y_bancos(client, contador):
    _asiento(client, contador, debe="1.1.01", haber="4.1.04", importe=5000, concepto="Cobro")
    _asiento(client, contador, debe="5.1.03", haber="1.1.02", importe=1200, concepto="Pago de servicios")

    r = client.get(f"{API}/libros/flujo-efectivo", headers=contador).json()

    assert r["entradas"] == 5000.0 and r["salidas"] == 1200.0 and r["neto"] == 3800.0
    assert r["saldosPorCuenta"]["1.1.01"] == 5000.0 and r["saldosPorCuenta"]["1.1.02"] == -1200.0
    assert any("Gastos administrativos" in m["contrapartida"] for m in r["movimientos"])


def test_posicion_de_iva_del_periodo(client, contador, interna):
    """Débito contra crédito fiscal: lo que hay que pagar."""
    for libro, tipo, neto, iva, cuentas in [
            ("VENTAS", "FACTURA_VENTA", 100000, 21000, [("1.2.01", "DEBE", "neto + iva"),
                                                         ("4.1.04", "HABER", "neto"), ("2.1.01", "HABER", "iva")]),
            ("COMPRAS", "FACTURA_COMPRA", 40000, 8400, [("5.1.03", "DEBE", "neto"), ("1.2.04", "DEBE", "iva"),
                                                         ("2.1.01", "HABER", "neto + iva")])]:
        client.post(f"{API}/definiciones", headers=contador, json={
            "modulo": "compras", "tipo": tipo, "nombre": tipo, "diario_codigo": "VAR",
            "lineas": [{"cuenta": c, "dc": dc, "importe": imp} for c, dc, imp in cuentas]})
        client.post("/internal/contabilidad/transacciones", headers=interna, json={
            "modulo": "compras", "tipo": tipo, "referencia": f"{tipo}-1", "fecha": HOY,
            "datos": {"neto": neto, "iva": iva,
                      "comprobante": {"libro": libro, "punto_venta": 1, "numero": 1, "cuit": "30712345678",
                                      "neto_gravado": neto, "iva": iva, "alicuota": 21,
                                      "total": neto + iva}}})

    r = client.get(f"{API}/libros/iva/posicion/periodo", headers=contador).json()

    assert r["debitoFiscal"] == 21000.0 and r["creditoFiscal"] == 8400.0
    assert r["saldo"] == 12600.0 and r["aPagar"] == 12600.0 and r["aFavor"] == 0.0
    assert r["ventas"]["comprobantes"] == 1 and r["compras"]["neto"] == 40000.0


def test_analisis_por_centro_de_costo(client, contador):
    client.post(f"{API}/centros", headers=contador, json={"codigo": "SUC1", "nombre": "Sucursal Centro"})
    client.post(f"{API}/centros", headers=contador, json={"codigo": "SUC2", "nombre": "Sucursal Valle"})
    _asiento(client, contador, debe="1.1.01", haber="4.1.04", importe=9000, centro="SUC1")
    _asiento(client, contador, debe="5.1.03", haber="1.1.01", importe=2000, centro="SUC1")
    _asiento(client, contador, debe="5.1.03", haber="1.1.01", importe=500, centro="SUC2")

    r = client.get(f"{API}/reportes/por-centro", headers=contador).json()

    suc1 = next(c for c in r["items"] if c["centro"] == "SUC1")
    assert suc1["nombre"] == "Sucursal Centro" and suc1["ingresos"] == 9000.0 and suc1["egresos"] == 2000.0
    assert suc1["resultado"] == 7000.0
    assert next(c for c in r["items"] if c["centro"] == "SUC2")["resultado"] == -500.0


def test_el_centro_de_costo_se_edita(client, contador):
    """Los centros base vienen sembrados (ADM, COM, FIN, SEG), como en el sistema anterior."""
    centros = client.get(f"{API}/centros", headers=contador).json()["items"]
    assert {c["codigo"] for c in centros} >= {"ADM", "COM", "FIN", "SEG"}
    assert client.post(f"{API}/centros", headers=contador,
                       json={"codigo": "ADM", "nombre": "Otra"}).status_code == 409
    c = next(x for x in centros if x["codigo"] == "ADM")
    r = client.put(f"{API}/centros/{c['id']}", headers=contador,
                   json={"codigo": "ADM", "nombre": "Administración general", "activo": False})
    assert r.json()["nombre"] == "Administración general" and r.json()["activo"] is False


# ── El plan sembrado es el del sistema anterior ──────────────────────────────────────────────────

def test_el_plan_es_el_del_sistema_anterior(client, contador):
    """Misma codificación que venía usando el motor de asientos de Créditos."""
    cuentas = {c["codigo"]: c for c in client.get(f"{API}/cuentas", headers=contador).json()["items"]}
    esperadas = {"1.1.01": "Caja", "1.1.02": "Banco", "1.1.05.01": "Préstamos otorgados",
                 "1.2.01": "Créditos a cobrar", "1.2.04": "IVA crédito fiscal",
                 "2.1.01": "IVA débito fiscal", "2.1.02": "Proveedores",
                 "3.3": "Resultado del ejercicio", "4.1.01": "Intereses ganados",
                 "4.1.02": "Intereses punitorios ganados", "4.1.03": "Seguros",
                 "4.1.04": "Gastos administrativos", "5.2.02": "Comisiones y gastos bancarios"}
    for codigo, nombre in esperadas.items():
        assert cuentas[codigo]["nombre"] == nombre, codigo
    assert cuentas["1"]["imputable"] is False and cuentas["1.1.01"]["imputable"] is True
    ej = client.get(f"{API}/ejercicios", headers=contador).json()["items"][0]
    assert ej["cuentaResultado"] == "3.3"


def test_una_siembra_vieja_se_alinea_con_el_plan(client, contador, db):
    """Si la base venía de un plan anterior: se corrigen los nombres y se van las cuentas sin uso."""
    from app.models import Cuenta
    from app.seed import sembrar
    db.add(Cuenta(codigo="9.9.90", nombre="Cuenta de otro plan", rubro="ACTIVO"))
    caja = db.query(Cuenta).filter_by(codigo="1.1.01").one()
    caja.nombre = "Caja chica (nombre viejo)"
    db.commit()

    sembrar(db)

    assert db.query(Cuenta).filter_by(codigo="9.9.90").first() is None      # no la usaba nadie
    assert db.query(Cuenta).filter_by(codigo="1.1.01").one().nombre == "Caja"


def test_una_cuenta_de_otro_plan_con_movimientos_no_se_borra(client, contador, db):
    from app.models import Cuenta
    from app.seed import sembrar
    db.add(Cuenta(codigo="9.9.91", nombre="Vieja con uso", rubro="ACTIVO"))
    db.commit()
    client.post(f"{API}/asientos", headers=contador, json={
        "fecha": HOY, "concepto": "Movimiento viejo",
        "lineas": [{"cuenta": "9.9.91", "debe": 100}, {"cuenta": "1.1.01", "haber": 100}]})

    sembrar(db)

    assert db.query(Cuenta).filter_by(codigo="9.9.91").first() is not None
