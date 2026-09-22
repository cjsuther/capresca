"""Libros y estados contables: diario, mayor, sumas y saldos, IVA y cierre de ejercicio."""
from datetime import date

from app import models
from tests.conftest import DEFINICION_DESEMBOLSO, transaccion

API = "/api/contabilidad"
HOY = date.today().isoformat()


def _asiento(client, contador, concepto="Ajuste", debe="1.1.01", haber="1.1.02", importe=1000.0, fecha=None):
    return client.post(f"{API}/asientos", headers=contador, json={
        "fecha": fecha or HOY, "concepto": concepto, "diario_codigo": "VAR",
        "lineas": [{"cuenta": debe, "debe": importe, "detalle": "sale"},
                   {"cuenta": haber, "haber": importe, "detalle": "entra"}]})


# ── Asientos manuales y partida doble ────────────────────────────────────────────────────────────

def test_el_asiento_manual_exige_partida_doble(client, contador):
    r = client.post(f"{API}/asientos", headers=contador, json={
        "fecha": HOY, "concepto": "Descuadrado",
        "lineas": [{"cuenta": "1.1.01", "debe": 100}, {"cuenta": "1.1.02", "haber": 90}]})
    assert r.status_code == 422 and "no balancea" in r.json()["detail"]


def test_una_linea_no_puede_ir_al_debe_y_al_haber(client, contador):
    r = client.post(f"{API}/asientos", headers=contador, json={
        "fecha": HOY, "concepto": "Rara",
        "lineas": [{"cuenta": "1.1.01", "debe": 100, "haber": 100}, {"cuenta": "1.1.02", "haber": 100}]})
    assert r.status_code == 422


def test_no_se_imputa_en_una_cuenta_de_agrupacion(client, contador):
    assert _asiento(client, contador, debe="1").status_code == 422


def test_no_se_asienta_fuera_de_un_ejercicio_abierto(client, contador):
    assert _asiento(client, contador, fecha="2019-05-05").status_code == 422
    assert "ejercicio" in _asiento(client, contador, fecha="2019-05-05").json()["detail"]


# ── Anulación (el libro no se edita) ─────────────────────────────────────────────────────────────

def test_un_asiento_se_anula_con_su_contra_asiento(client, contador, db):
    a = _asiento(client, contador).json()
    r = client.post(f"{API}/asientos/{a['id']}/anular", headers=contador, json={"motivo": "cargado mal"}).json()
    assert r["anulado"]["estado"] == "ANULADO"
    rev = r["reversa"]
    assert rev["origen"] == "REVERSA" and rev["reversaDe"] == a["id"]
    assert [(l["cuenta"], l["debe"], l["haber"]) for l in rev["lineas"]] == [
        ("1.1.01", 0.0, 1000.0), ("1.1.02", 1000.0, 0.0)]
    assert client.post(f"{API}/asientos/{a['id']}/anular", headers=contador, json={}).status_code == 422


def test_al_anular_el_asiento_de_una_transaccion_esta_queda_anulada(client, interna, contador, db):
    client.post(f"{API}/definiciones", headers=contador, json=DEFINICION_DESEMBOLSO)
    r = client.post("/internal/contabilidad/transacciones", headers=interna, json=transaccion()).json()
    client.post(f"{API}/asientos/{r['asientoId']}/anular", headers=contador, json={"motivo": "se revirtió"})
    t = db.get(models.Transaccion, r["id"])
    assert t.estado == "ANULADA" and "se revirtió" in t.motivo


# ── Libros ───────────────────────────────────────────────────────────────────────────────────────

def test_libro_diario_y_mayor(client, contador):
    _asiento(client, contador, concepto="Uno", importe=1500)
    _asiento(client, contador, concepto="Dos", importe=500)

    diario = client.get(f"{API}/libros/diario", headers=contador).json()
    assert [a["concepto"] for a in diario["items"]] == ["Uno", "Dos"]
    assert diario["items"][0]["debe"] == diario["items"][0]["haber"] == 1500.0

    mayor = client.get(f"{API}/libros/mayor/1.1.01", headers=contador).json()
    assert mayor["cuenta"]["nombre"] == "Caja"
    assert [m["saldo"] for m in mayor["movimientos"]] == [1500.0, 2000.0]
    assert mayor["saldoFinal"] == 2000.0


def test_el_mayor_de_una_cuenta_inexistente_avisa(client, contador):
    assert client.get(f"{API}/libros/mayor/9.9.99", headers=contador).status_code == 422


def test_sumas_y_saldos_cierra(client, contador):
    _asiento(client, contador, importe=2500)
    r = client.get(f"{API}/libros/sumas-y-saldos", headers=contador).json()
    assert r["balanceado"] is True
    assert r["totales"]["debe"] == r["totales"]["haber"] == 2500.0
    assert r["totales"]["saldoDeudor"] == r["totales"]["saldoAcreedor"] == 2500.0


def test_el_anulado_y_su_contra_asiento_quedan_en_el_libro_y_se_compensan(client, contador):
    """El libro es inalterable: el anulado sigue figurando y la reversa lo neutraliza."""
    a = _asiento(client, contador, importe=800).json()
    client.post(f"{API}/asientos/{a['id']}/anular", headers=contador, json={})

    mayor = client.get(f"{API}/libros/mayor/1.1.01", headers=contador).json()
    assert [m["debe"] for m in mayor["movimientos"]] == [800.0, 0.0]
    assert mayor["saldoFinal"] == 0.0

    diario = client.get(f"{API}/libros/diario", headers=contador).json()
    assert [(x["origen"], x["estado"]) for x in diario["items"]] == [("MANUAL", "ANULADO"), ("REVERSA", "REGISTRADO")]
    # "Lo que quedó vigente" es otra vista, para mirar, no el libro.
    vigentes = client.get(f"{API}/asientos?solo_vigentes=true", headers=contador).json()
    assert [x["origen"] for x in vigentes["items"]] == ["REVERSA"]


def test_estados_contables(client, contador):
    # Cobro de un servicio: entra plata (activo) contra un ingreso.
    client.post(f"{API}/asientos", headers=contador, json={
        "fecha": HOY, "concepto": "Cobro de servicio",
        "lineas": [{"cuenta": "1.1.01", "debe": 10000}, {"cuenta": "4.1.04", "haber": 10000}]})
    client.post(f"{API}/asientos", headers=contador, json={
        "fecha": HOY, "concepto": "Gasto bancario",
        "lineas": [{"cuenta": "5.1.01", "debe": 1500}, {"cuenta": "1.1.01", "haber": 1500}]})

    r = client.get(f"{API}/libros/estados", headers=contador).json()

    assert r["situacion"]["activo"]["total"] == 8500.0
    assert r["resultados"]["ingresos"]["total"] == 10000.0
    assert r["resultados"]["egresos"]["total"] == 1500.0
    assert r["resultados"]["resultado"] == 8500.0
    assert r["situacion"]["ecuacionCierra"] is True


# ── Libro IVA ────────────────────────────────────────────────────────────────────────────────────

def test_la_transaccion_con_comprobante_alimenta_el_libro_iva(client, interna, contador):
    client.post(f"{API}/definiciones", headers=contador, json={
        "modulo": "creditos", "tipo": "FACTURA", "nombre": "Factura de servicios", "diario_codigo": "VTA",
        "leyenda": "Factura {referencia}",
        "lineas": [{"cuenta": "1.1.03", "dc": "DEBE", "importe": "neto + iva"},
                   {"cuenta": "4.1.04", "dc": "HABER", "importe": "neto"},
                   {"cuenta": "2.1.02", "dc": "HABER", "importe": "iva"}]})
    client.post("/internal/contabilidad/transacciones", headers=interna, json=transaccion(
        tipo="FACTURA", referencia="A-0001-00000123",
        datos={"neto": 100000, "iva": 21000,
               "comprobante": {"libro": "VENTAS", "tipo_comprobante": "01", "punto_venta": 1,
                               "numero": 123, "cuit": "30-71234567-8", "razon_social": "ACME SA",
                               "condicion_iva": "RESPONSABLE_INSCRIPTO", "neto_gravado": 100000,
                               "alicuota": 21, "iva": 21000, "total": 121000}}))

    r = client.get(f"{API}/libros/iva/VENTAS", headers=contador).json()

    assert r["totales"] == {"netoGravado": 100000.0, "netoNoGravado": 0.0, "exento": 0.0, "iva": 21000.0,
                            "percepciones": 0.0, "retenciones": 0.0, "total": 121000.0}
    assert r["porAlicuota"] == [{"alicuota": 21.0, "neto": 100000.0, "iva": 21000.0}]
    assert r["items"][0]["cuit"] == "30712345678" and r["items"][0]["asientoId"]
    assert client.get(f"{API}/libros/iva/OTRO", headers=contador).status_code == 422


# ── Ejercicios ───────────────────────────────────────────────────────────────────────────────────

def test_no_se_pueden_superponer_ejercicios(client, contador):
    anio = date.today().year
    r = client.post(f"{API}/ejercicios", headers=contador, json={
        "numero": anio + 1, "desde": f"{anio}-06-01", "hasta": f"{anio + 1}-05-31"})
    assert r.status_code == 409 and "superpone" in r.json()["detail"]


def test_el_cierre_refunde_los_resultados_y_bloquea_el_ejercicio(client, contador, db):
    client.post(f"{API}/asientos", headers=contador, json={
        "fecha": HOY, "concepto": "Cobro", "lineas": [{"cuenta": "1.1.01", "debe": 5000},
                                                       {"cuenta": "4.1.04", "haber": 5000}]})
    ej = client.get(f"{API}/ejercicios", headers=contador).json()["items"][0]

    r = client.post(f"{API}/ejercicios/{ej['id']}/cerrar", headers=contador).json()

    assert r["resultado"] == 5000.0 and r["asientoCierre"]
    estados = client.get(f"{API}/libros/estados", headers=contador).json()
    assert estados["resultados"]["resultado"] == 0.0          # los resultados quedaron refundidos
    assert _asiento(client, contador).status_code == 422       # ejercicio cerrado: no admite asientos
    assert client.post(f"{API}/ejercicios/{ej['id']}/cerrar", headers=contador).status_code == 422


def test_no_se_cierra_con_transacciones_sin_contabilizar(client, interna, contador):
    client.post("/internal/contabilidad/transacciones", headers=interna, json=transaccion())
    ej = client.get(f"{API}/ejercicios", headers=contador).json()["items"][0]
    r = client.post(f"{API}/ejercicios/{ej['id']}/cerrar", headers=contador)
    assert r.status_code == 422 and "sin contabilizar" in r.json()["detail"]


def test_el_resumen_muestra_el_estado_del_modulo(client, interna, contador):
    client.post("/internal/contabilidad/transacciones", headers=interna, json=transaccion())
    r = client.get(f"{API}/resumen", headers=contador).json()
    assert r["pendientesConfiguracion"] == 1 and r["ejercicio"]["estado"] == "ABIERTO"
    assert r["cuentas"] > 20 and r["asientos"] == 0
