"""Flujo del módulo Caja: cobranza de cuotas, mora e emisión de recibo."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_caja.db"
os.environ["ENVIRONMENT"] = "development"

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


def _credito_otorgado(client, h, cuotas=6, primer_vto="2026-01-10"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)  # francés con mora
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"],
        "monto_solicitado": "120000", "cantidad_cuotas": cuotas,
        "fecha_primer_vencimiento": primer_vto,
    }).json()
    cred = client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()
    return cred


def test_cobranza_sin_mora(client):
    h = _auth(client)
    cred = _credito_otorgado(client, h)
    cid = cred["id"]

    # pendientes al día del primer vencimiento: sin mora
    pend = client.get(f"/api/creditos/caja/creditos/{cid}/pendientes?fecha_pago=2026-01-10",
                      headers=h).json()
    assert len(pend) == 6
    assert pend[0]["dias_mora"] == 0
    assert pend[0]["interes_punitorio"] == "0.00"

    # cobrar la cuota 1
    r = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-01-10",
        "via_pago": "EFECTIVO",
    })
    assert r.status_code == 201, r.text
    recibo = r.json()
    assert recibo["numero"] >= 1
    assert len(recibo["pagos"]) == 1
    assert recibo["pagos"][0]["interes_punitorio"] == "0.00"

    # la cuota 1 ya no figura pendiente
    pend2 = client.get(f"/api/creditos/caja/creditos/{cid}/pendientes", headers=h).json()
    assert all(p["numero"] != 1 for p in pend2)


def test_cobranza_con_mora(client):
    h = _auth(client)
    cred = _credito_otorgado(client, h)
    cid = cred["id"]

    # pagar la cuota 1 con 30 días de atraso -> aparece punitorio
    pend = client.get(f"/api/creditos/caja/creditos/{cid}/pendientes?fecha_pago=2026-02-09",
                      headers=h).json()
    c1 = next(p for p in pend if p["numero"] == 1)
    assert c1["dias_mora"] == 30
    assert float(c1["interes_punitorio"]) > 0
    # IVA punitorio = 21% del punitorio (regla validada contra ivacob.DBF)
    from decimal import Decimal, ROUND_HALF_UP
    ip = Decimal(c1["interes_punitorio"])
    assert Decimal(c1["iva_punitorio"]) == (ip * Decimal("21") / 100).quantize(
        Decimal("0.01"), ROUND_HALF_UP)

    r = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-02-09",
    })
    assert r.status_code == 201
    pago = r.json()["pagos"][0]
    assert pago["dias_mora"] == 30
    assert float(pago["interes_punitorio"]) > 0


def test_cancelacion_total(client):
    h = _auth(client)
    cred = _credito_otorgado(client, h, cuotas=3)
    cid = cred["id"]

    r = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1, 2, 3], "fecha_pago": "2026-01-10",
    })
    assert r.status_code == 201
    # el crédito queda cancelado y sin saldo
    c = client.get(f"/api/creditos/creditos/{cid}", headers=h).json()
    assert c["estado"] == "C"
    assert Decimal_(c["saldo_capital"]) == 0

    # no se puede volver a cobrar
    r2 = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-01-10",
    })
    assert r2.status_code == 409


def test_recalculo_vencimientos(client):
    """Recálculo modo 'vencimientos' (recaotros): sólo reprograma fecha_vto de las
    cuotas no pagadas; no toca capital/interés ni cuotas pagadas."""
    h = _auth(client)
    from decimal import Decimal
    cred = _credito_otorgado(client, h, cuotas=6, primer_vto="2026-01-10")
    cid = cred["id"]
    # pagar la cuota 1 (queda pagada, no se debe tocar)
    client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-01-10"})

    # preview: reprograma las pendientes a partir de 2026-03-15 (cuota N -> +N-1 meses)
    prev = client.get(f"/api/creditos/creditos/{cid}/recalculo?modo=vencimientos&primer_vto=2026-03-15",
                      headers=h).json()
    assert prev["cantidad_actual"] == 5   # cuotas 2..6 (la 1 está pagada)
    # el total no cambia (sólo fechas); capital/interés iguales
    assert Decimal(prev["total_actual"]) == Decimal(prev["total_propuesto"])
    prop2 = next(p for p in prev["propuesto"] if p["numero"] == 2)
    assert prop2["fecha_vto"] == "2026-04-15"   # cuota 2 -> 2026-03-15 + 1 mes

    # aplicar
    r = client.post(f"/api/creditos/creditos/{cid}/recalculo", headers=h,
                    json={"modo": "vencimientos", "primer_vto": "2026-03-15"})
    assert r.status_code == 200, r.text
    # la cuota 2 ahora vence 2026-04-15; la 1 (pagada) intacta
    pend = client.get(f"/api/creditos/caja/creditos/{cid}/pendientes", headers=h).json()
    c2 = next(p for p in pend if p["numero"] == 2)
    assert c2["fecha_vencimiento"] == "2026-04-15"


def test_recalculo_jubilatorio_capital_puro(client):
    """Recálculo modo 'jubilatorio' (recaportes): regenera el plan pendiente como
    capital puro (interés 0), cuota = 10% del haber, última = resto."""
    h = _auth(client)
    from decimal import Decimal
    cred = _credito_otorgado(client, h, cuotas=6)
    cid = cred["id"]
    cap = Decimal(str(cred["capital"]))   # 120000

    # haber 100000 -> cuota = 10000; saldo = capital (nada pagado) -> 12 cuotas
    prev = client.get(f"/api/creditos/creditos/{cid}/recalculo?modo=jubilatorio&haber=100000",
                      headers=h).json()
    assert all(Decimal(p["interes"]) == 0 for p in prev["propuesto"])
    assert Decimal(prev["total_propuesto"]) == cap   # capital puro suma el saldo
    # cantidad = ceil(120000/10000) = 12
    assert prev["cantidad_propuesta"] == 12
    assert all(Decimal(p["capital"]) == Decimal("10000.00") for p in prev["propuesto"])

    # aplicar y verificar
    r = client.post(f"/api/creditos/creditos/{cid}/recalculo", headers=h,
                    json={"modo": "jubilatorio", "haber": "100000"})
    assert r.status_code == 200 and r.json()["cuotas_resultantes"] == 12


def test_baja_credito(client):
    """Baja/anulación de crédito (32565): motivo obligatorio, no si hay cuotas pagadas,
    marca estado B y anula las cuotas."""
    h = _auth(client)
    cred = _credito_otorgado(client, h, cuotas=4)
    cid = cred["id"]

    # sin motivo -> 422 (validación) ; motivo vacío -> 409
    assert client.post(f"/api/creditos/creditos/{cid}/baja", headers=h, json={}).status_code == 422
    assert client.post(f"/api/creditos/creditos/{cid}/baja", headers=h, json={"motivo": "   "}).status_code == 409

    # baja con motivo -> estado B
    r = client.post(f"/api/creditos/creditos/{cid}/baja", headers=h,
                    json={"motivo": "Cargado por error"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "B"
    # ya no aparece pendiente
    assert not client.get(f"/api/creditos/caja/creditos/{cid}/pendientes", headers=h).json()
    # no se puede re-dar de baja
    assert client.post(f"/api/creditos/creditos/{cid}/baja", headers=h,
                       json={"motivo": "otra"}).status_code == 409


def test_baja_credito_con_pagos_rechazada(client):
    """No se puede dar de baja un crédito con cuotas pagadas (va cancelación)."""
    h = _auth(client)
    cred = _credito_otorgado(client, h, cuotas=4)
    cid = cred["id"]
    client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-01-10"})
    r = client.post(f"/api/creditos/creditos/{cid}/baja", headers=h, json={"motivo": "x"})
    assert r.status_code == 409 and "cancelación" in r.json()["detail"].lower()


def test_cancelacion_anticipada_credito(client):
    """Cancelación anticipada (32045): salda todas las cuotas, condona el interés
    futuro no devengado (cuotas no vencidas pagan sólo capital) y deja el crédito en C."""
    h = _auth(client)
    from decimal import Decimal
    cred = _credito_otorgado(client, h, cuotas=6, primer_vto="2026-01-10")
    cid = cred["id"]

    # cuotas del plan y suma total "normal" (con todo el interés)
    pend = client.get(f"/api/creditos/caja/creditos/{cid}/pendientes?fecha_pago=2026-01-05", headers=h).json()
    total_normal = sum(Decimal(str(p["importe_cuota"])) for p in pend)

    # simular cancelación al 2026-01-05 (ninguna cuota vencida aún -> sólo capital)
    det = client.get(f"/api/creditos/creditos/{cid}/cancelacion?fecha=2026-01-05", headers=h).json()
    assert det["cantidad_cuotas"] == 6
    assert Decimal(det["punitorio"]) == Decimal("0.00")
    # el total a cancelar es MENOR que pagar todas las cuotas normalmente (se condona
    # el interés futuro) y == al capital pendiente
    assert Decimal(det["total"]) == Decimal(det["capital"])
    assert Decimal(det["total"]) <= total_normal

    # cancelar
    r = client.post(f"/api/creditos/creditos/{cid}/cancelar", headers=h, json={
        "fecha_pago": "2026-01-05", "via_pago": "EFECTIVO"})
    assert r.status_code == 201, r.text
    assert len(r.json()["pagos"]) == 6

    # el crédito queda en C, sin saldo, sin cuotas pendientes
    c = client.get(f"/api/creditos/creditos/{cid}", headers=h).json()
    assert c["estado"] == "C" and Decimal(str(c["saldo_capital"])) == 0
    assert not client.get(f"/api/creditos/caja/creditos/{cid}/pendientes", headers=h).json()

    # no se puede re-cancelar
    assert client.post(f"/api/creditos/creditos/{cid}/cancelar", headers=h, json={
        "fecha_pago": "2026-01-05"}).status_code == 409


def test_cola_de_caja_por_persona_multicredito(client):
    """Cola de caja (22515): agrupa por persona las cuotas pendientes de TODOS sus
    créditos y las cobra en un solo recibo."""
    h = _auth(client)
    # dos créditos del MISMO cliente (el primero de la lista)
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]
    cid1 = _credito_otorgado(client, h, cuotas=3)["id"]
    cid2 = _credito_otorgado(client, h, cuotas=3)["id"]
    assert cli["id"]  # sanity

    # la cola por CUIL trae cuotas de ambos créditos
    cola = client.get(f"/api/creditos/caja/cola?cuil={cli['cuil']}&fecha=2026-01-10",
                      headers=h).json()
    creditos_en_cola = {it["credito_id"] for it in cola["items"]}
    assert {cid1, cid2} <= creditos_en_cola
    assert cola["cantidad"] >= 6

    # cobrar la cuota 1 de cada crédito en UN recibo
    r = client.post("/api/creditos/caja/cola/cobrar", headers=h, json={
        "items": [{"credito_id": cid1, "cuotas": [1]},
                  {"credito_id": cid2, "cuotas": [1]}],
        "fecha_pago": "2026-01-10", "via_pago": "EFECTIVO",
    })
    assert r.status_code == 201, r.text
    recibo = r.json()
    assert len(recibo["pagos"]) == 2  # una cuota de cada crédito, mismo recibo

    # anular el recibo revierte AMBOS créditos
    an = client.post(f"/api/creditos/caja/recibos/{recibo['id']}/anular", headers=h).json()
    assert an["estado"] == "A"
    # las cuotas 1 vuelven a estar pendientes en los dos créditos
    for cid in (cid1, cid2):
        pend = client.get(f"/api/creditos/caja/creditos/{cid}/pendientes", headers=h).json()
        assert any(p["numero"] == 1 for p in pend)


def test_cierre_incluye_quiniela_por_moneda(client):
    """Cierre de caja (22535): totaliza los cobros de créditos (pesos) y los de
    quiniela (bonos/pesos) del día, separados por moneda."""
    h = _auth(client)
    from app.core.database import SessionLocal
    from app import models
    from decimal import Decimal
    # cobro de crédito del día 2026-01-10
    cid = _credito_otorgado(client, h, cuotas=3)["id"]
    r = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-01-10"}).json()
    total_credito = Decimal(str(r["total"]))
    # cobro de agencia de quiniela el mismo día (sembrado directo)
    import datetime
    db = SessionLocal()
    db.add(models.CajaPagoAgencia(
        cod_agencia=7777, fecha_pago=datetime.date(2026, 1, 10), no_recibo=90001,
        bonos=Decimal("5000"), pesos=Decimal("20000"), total=Decimal("25000"),
        cobrado_bonos=Decimal("5000"), cobrado_pesos=Decimal("20000"),
        cobrado_total=Decimal("25000"), cajero="admin", anulado=False))
    db.commit(); db.close()

    c = client.get("/api/creditos/caja/cierre?fecha=2026-01-10", headers=h).json()
    monedas = {m["concepto"]: Decimal(m["importe"]) for m in c["por_moneda"]}
    assert monedas["Bonos"] == Decimal("5000.00")
    assert monedas["Pesos"] == total_credito + Decimal("20000.00")
    assert c["quiniela_cantidad"] == 1
    assert Decimal(c["quiniela_cobrado"]) == Decimal("25000.00")
    assert Decimal(c["total_cobrado"]) == total_credito + Decimal("25000.00")


def test_cobranzas_periodo_unifica_creditos_y_quiniela(client):
    """Informe de cobranzas en período (23065): recibos de créditos + cobros de
    quiniela entre dos fechas, con totales separados."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    cid = _credito_otorgado(client, h, cuotas=3)["id"]
    r = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-03-15"}).json()
    total_cred = Decimal(str(r["total"]))
    db = SessionLocal()
    db.add(models.CajaPagoAgencia(
        cod_agencia=8888, fecha_pago=datetime.date(2026, 3, 15), no_recibo=95000,
        cobrado_total=Decimal("40000"), cobrado_pesos=Decimal("40000"),
        cajero="admin", anulado=False))
    db.commit(); db.close()

    inf = client.get("/api/creditos/caja/cobranzas-periodo?desde=2026-03-01&hasta=2026-03-31",
                     headers=h).json()
    assert Decimal(inf["total_creditos"]) == total_cred
    assert Decimal(inf["total_quiniela"]) == Decimal("40000.00")
    assert Decimal(inf["total"]) == total_cred + Decimal("40000.00")
    origenes = {it["origen"] for it in inf["items"]}
    assert origenes == {"CR", "JUEG"}
    # filtro por origen
    solo_ju = client.get("/api/creditos/caja/cobranzas-periodo?desde=2026-03-01&hasta=2026-03-31&origen=JUEG",
                         headers=h).json()
    assert all(it["origen"] == "JUEG" for it in solo_ju["items"])


def test_recaudacion_anual_por_origen_y_mes(client):
    """Recaudación anual (23030): totales por origen (CR/JUEG) y mes del año."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    # cobro de crédito en marzo 2026
    cid = _credito_otorgado(client, h, cuotas=3)["id"]
    r = client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-03-15"}).json()
    total_cr = Decimal(str(r["total"]))
    # cobros de quiniela en marzo y julio 2026
    db = SessionLocal()
    db.add(models.CajaPagoAgencia(cod_agencia=1, fecha_pago=datetime.date(2026, 3, 10),
        no_recibo=96001, cobrado_total=Decimal("10000"), premios_pesos=Decimal("-2000"),
        cajero="admin", anulado=False))
    db.add(models.CajaPagoAgencia(cod_agencia=2, fecha_pago=datetime.date(2026, 7, 5),
        no_recibo=96002, cobrado_total=Decimal("30000"), cajero="admin", anulado=False))
    db.commit(); db.close()

    d = client.get("/api/creditos/caja/recaudacion-anual?anio=2026", headers=h).json()
    porig = {o["origen"]: o for o in d["origenes"]}
    # CR: total en marzo (índice 2)
    assert Decimal(porig["CR"]["meses"][2]) == total_cr
    assert Decimal(porig["CR"]["total"]) == total_cr
    # JUEG: marzo 10000 + julio 30000
    assert Decimal(porig["JUEG"]["meses"][2]) == Decimal("10000.00")
    assert Decimal(porig["JUEG"]["meses"][6]) == Decimal("30000.00")
    assert Decimal(porig["JUEG"]["total"]) == Decimal("40000.00")
    assert Decimal(porig["JUEG"]["premios"][2]) == Decimal("-2000.00")
    assert Decimal(d["total_general"]) == total_cr + Decimal("40000.00")


def test_reimpresion_cierre_y_control_pdf(client):
    """Reimpresión de cierre (23040) y control de caja por cajero (23060): ambos
    devuelven PDF; el cierre incluye el desglose por moneda + quiniela."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    # un cobro de crédito + uno de quiniela el mismo día
    cid = _credito_otorgado(client, h, cuotas=3)["id"]
    client.post("/api/creditos/caja/cobrar", headers=h, json={
        "credito_id": cid, "cuotas": [1], "fecha_pago": "2026-04-10"})
    db = SessionLocal()
    db.add(models.CajaPagoAgencia(cod_agencia=1, fecha_pago=datetime.date(2026, 4, 10),
        no_recibo=90100, cobrado_total=Decimal("12000"), cobrado_pesos=Decimal("12000"),
        cajero="admin", anulado=False))
    db.commit(); db.close()

    # 23040: reimpresión de cierre a una fecha (PDF con por_moneda + quiniela)
    r1 = client.get("/api/creditos/caja/cierre/pdf?fecha=2026-04-10", headers=h)
    assert r1.status_code == 200 and r1.content[:4] == b"%PDF"
    # 23060: reimpresión control de caja del cajero
    r2 = client.get("/api/creditos/caja/control/pdf?fecha=2026-04-10&cajero=admin", headers=h)
    assert r2.status_code == 200 and r2.content[:4] == b"%PDF"


def test_recibos_del_dia(client):
    """Reimpresión de recibos (23010): unifica recibos de quiniela (cajapagos) y de
    créditos (cajacreseg agrupado por no_recibo) de un día."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.CajaPagoAgencia(cod_agencia=500, fecha_pago=datetime.date(2026, 6, 20),
        no_recibo=70001, cobrado_total=Decimal("15000"), cajero="ana", anulado=False))
    # dos ítems de cajacreseg del mismo recibo -> se agrupan
    for _ in range(2):
        db.add(models.CajaCreSeg(origen="CRED", no_recibo=70002, apellido_nombre="PEREZ",
            pagado=True, revertida=False, total_gral=Decimal("1000"), cajero="ana",
            fecha_pago=datetime.date(2026, 6, 20)))
    db.commit(); db.close()

    d = client.get("/api/creditos/caja/recibos-del-dia?fecha=2026-06-20", headers=h).json()
    recibos = {(i["no_recibo"], i["origen"]): i for i in d["items"]}
    assert Decimal(recibos[(70001, "JUEG")]["importe"]) == Decimal("15000.00")
    assert Decimal(recibos[(70002, "CRED")]["importe"]) == Decimal("2000.00")  # 2 ítems sumados
    assert d["cantidad"] == 2
    assert Decimal(d["total"]) == Decimal("17000.00")


def test_reimprimir_recibo_pdf(client):
    """Reimpresión de recibo (23010): regenera el PDF desde los datos, para quiniela
    (cajapagos+cajaliq) y para créditos (cajacreseg)."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    # recibo de quiniela con una liquidación
    db.add(models.CajaPagoAgencia(cod_agencia=600, fecha_pago=datetime.date(2026, 6, 21),
        no_recibo=80001, cobrado_total=Decimal("5000"), cobrado_pesos=Decimal("5000"),
        cajero="ana", anulado=False))
    db.add(models.LiquidacionAgencia(cod_agencia=600, no_agencia=1, cod_juego=10,
        juego="Quiniela", no_sorteo=1, moneda="$", total_gral=Decimal("5000"),
        pagado=True, no_recibo=80001, fecha_pago=datetime.date(2026, 6, 21)))
    # recibo de crédito
    db.add(models.CajaCreSeg(origen="CRED", no_credito=9, no_recibo=80002,
        apellido_nombre="LOPEZ", cuota=3, moncuo=Decimal("900"), interes=Decimal("100"),
        total_gral=Decimal("1000"), pagado=True, revertida=False, cajero="ana",
        fecha_pago=datetime.date(2026, 6, 21)))
    db.commit(); db.close()

    # PDF quiniela
    r1 = client.get("/api/creditos/caja/recibos-del-dia/reimprimir?no_recibo=80001&origen=JUEG&fecha=2026-06-21", headers=h)
    assert r1.status_code == 200 and r1.content[:4] == b"%PDF"
    # PDF crédito
    r2 = client.get("/api/creditos/caja/recibos-del-dia/reimprimir?no_recibo=80002&origen=CRED&fecha=2026-06-21", headers=h)
    assert r2.status_code == 200 and r2.content[:4] == b"%PDF"
    # inexistente -> 404
    r3 = client.get("/api/creditos/caja/recibos-del-dia/reimprimir?no_recibo=99999&origen=CRED&fecha=2026-06-21", headers=h)
    assert r3.status_code == 404


def test_pagos_realizados(client):
    """Listado de pagos realizados (23025): cajacreseg en rango de fechas, filtrable
    por coding y texto; excluye revertidos."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.CajaCreSeg(origen="CRED", no_credito=1, apellido_nombre="PEREZ JUAN",
        coding=50, subing=1, pagado=True, revertida=False, total_gral=Decimal("1000"),
        fecha_pago=datetime.date(2026, 6, 5)))
    db.add(models.CajaCreSeg(origen="CRED", no_credito=2, apellido_nombre="GOMEZ ANA",
        coding=80, subing=1, pagado=True, revertida=False, total_gral=Decimal("2000"),
        fecha_pago=datetime.date(2026, 6, 6)))
    db.add(models.CajaCreSeg(origen="CRED", no_credito=3, apellido_nombre="PEREZ LUIS",
        coding=50, pagado=True, revertida=True, total_gral=Decimal("9999"),  # revertido
        fecha_pago=datetime.date(2026, 6, 7)))
    db.commit(); db.close()

    # todo el rango: 2 (excluye revertido)
    d = client.get("/api/creditos/caja/pagos-realizados?desde=2026-06-01&hasta=2026-06-30", headers=h).json()
    assert d["cantidad"] == 2
    assert Decimal(d["total"]) == Decimal("3000.00")
    # filtro por coding=50 -> sólo PEREZ JUAN
    d2 = client.get("/api/creditos/caja/pagos-realizados?desde=2026-06-01&hasta=2026-06-30&coding=50", headers=h).json()
    assert d2["cantidad"] == 1 and d2["items"][0]["apellido_nombre"] == "PEREZ JUAN"
    # filtro por texto
    d3 = client.get("/api/creditos/caja/pagos-realizados?desde=2026-06-01&hasta=2026-06-30&texto=gomez", headers=h).json()
    assert d3["cantidad"] == 1 and d3["items"][0]["apellido_nombre"] == "GOMEZ ANA"


def test_planilla_contable_creditos(client):
    """Planilla contable de créditos cobrados en un día (23045): descompone los
    cobros CRED del día por concepto contable."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.CajaCreSeg(origen="CRED", no_credito=1, pagado=True, revertida=False,
        moncuo=Decimal("1000"), interes=Decimal("100"), iva_interes=Decimal("21"),
        seguro=Decimal("50"), interes_punit=Decimal("30"), iva_punit=Decimal("6.30"),
        total_gral=Decimal("1207.30"), fecha_pago=datetime.date(2026, 6, 10)))
    db.add(models.CajaCreSeg(origen="SEGU", no_credito=0, pagado=True, revertida=False,
        moncuo=Decimal("999"), total_gral=Decimal("999"),  # SEGU -> no cuenta
        fecha_pago=datetime.date(2026, 6, 10)))
    db.commit(); db.close()

    d = client.get("/api/creditos/caja/planilla-contable-creditos?fecha=2026-06-10", headers=h).json()
    conc = {c["concepto"]: Decimal(c["importe"]) for c in d["conceptos"]}
    assert d["cantidad"] == 1               # sólo el CRED
    assert conc["Capital"] == Decimal("1000.00")
    assert conc["Interés punitorio"] == Decimal("30.00")
    assert conc["IVA s/punitorio"] == Decimal("6.30")
    assert Decimal(d["total"]) == Decimal("1207.30")


def test_intereses_iva_mensual(client):
    """Reporte mensual de intereses e IVA (23015): combina créditos (cajacreseg) y
    quiniela (cajaliq) del mes, por origen."""
    h = _auth(client)
    import datetime
    from decimal import Decimal
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    # crédito: interés normal 100 + iva 21, punitorio 50 + iva 10,5, pagado en jun-2025
    db.add(models.CajaCreSeg(origen="CRED", no_credito=1, pagado=True, revertida=False,
        interes=Decimal("100"), iva_interes=Decimal("21"),
        interes_punit=Decimal("50"), iva_punit=Decimal("10.50"),
        fecha_pago=datetime.date(2025, 6, 10)))
    # revertida -> no cuenta
    db.add(models.CajaCreSeg(origen="CRED", no_credito=2, pagado=True, revertida=True,
        interes=Decimal("999"), fecha_pago=datetime.date(2025, 6, 11)))
    # quiniela con interés/iva en jun-2025
    db.add(models.LiquidacionAgencia(cod_agencia=1, no_agencia=1, juego="Q", no_sorteo=1,
        intereses=Decimal("200"), iva=Decimal("42"), pagado=True,
        fecha_pago=datetime.date(2025, 6, 12)))
    db.commit(); db.close()

    d = client.get("/api/creditos/caja/intereses-iva-mensual?mes=6&anio=2025", headers=h).json()
    por = {i["origen"]: i for i in d["items"]}
    assert Decimal(por["CRED"]["total_interes"]) == Decimal("150.00")   # 100 + 50
    assert Decimal(por["CRED"]["total_iva"]) == Decimal("31.50")        # 21 + 10.5
    assert Decimal(por["JUEG"]["total_interes"]) == Decimal("200.00")
    assert Decimal(por["JUEG"]["total_iva"]) == Decimal("42.00")
    assert Decimal(d["total_interes"]) == Decimal("350.00")
    assert Decimal(d["total_iva"]) == Decimal("73.50")


def Decimal_(x):
    from decimal import Decimal
    return Decimal(str(x))


def teardown_module(_):
    if os.path.exists("_caja.db"):
        os.remove("_caja.db")
