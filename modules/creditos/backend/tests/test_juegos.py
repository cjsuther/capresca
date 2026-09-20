"""Módulo Juegos/Quiniela: agencias, liquidaciones, resumen, cobro."""
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app import models


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(client):
    r = client.post("/api/creditos/auth/login", data={"username": "admin", "password": "admin123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _sembrar_liquidacion(pagado=False):
    db = SessionLocal()
    db.add(models.AgenciaJuego(numero=10, subagencia=0, interior=False, quiniela=True))
    liq = models.LiquidacionAgencia(
        no_agencia=10, juego="QUINIELA", no_sorteo=5001,
        fecha_sorteo=None, recaudacion=Decimal("100000"), premios=Decimal("60000"),
        comision_agencia=Decimal("12000"), multas=Decimal("0"),
        total=Decimal("28000"), pagado=pagado)
    db.add(liq)
    db.commit()
    lid = liq.id
    db.close()
    return lid


def test_agencias_y_resumen(client):
    h = _auth(client)
    _sembrar_liquidacion()
    ags = client.get("/api/creditos/juegos/agencias", headers=h).json()
    assert any(a["numero"] == 10 and a["quiniela"] for a in ags)
    r = client.get("/api/creditos/juegos/resumen", headers=h).json()
    assert Decimal(r["recaudacion"]) >= Decimal("100000")
    assert Decimal(r["premios"]) >= Decimal("60000")


def test_cobrar_liquidacion(client):
    h = _auth(client)
    lid = _sembrar_liquidacion(pagado=False)
    r = client.post(f"/api/creditos/juegos/liquidaciones/{lid}/cobrar?no_recibo=777", headers=h)
    assert r.status_code == 200
    assert r.json()["pagado"] is True and r.json()["no_recibo"] == 777
    # no se puede recobrar
    assert client.post(f"/api/creditos/juegos/liquidaciones/{lid}/cobrar?no_recibo=778", headers=h).status_code == 409


def test_cobrar_liquidacion_idempotente(client):
    """H-157: cobrar una liquidación es idempotente — doble-POST con la misma Idempotency-Key devuelve el
    mismo resultado, no cobra dos veces."""
    h = _auth(client)
    lid = _sembrar_liquidacion(pagado=False)
    hk = {**h, "Idempotency-Key": "liq-cobrar-k1"}
    r1 = client.post(f"/api/creditos/juegos/liquidaciones/{lid}/cobrar?no_recibo=901", headers=hk)
    r2 = client.post(f"/api/creditos/juegos/liquidaciones/{lid}/cobrar?no_recibo=901", headers=hk)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["pagado"] is True and r2.json()["no_recibo"] == 901


def test_filtro_liquidaciones_pendientes(client):
    h = _auth(client)
    _sembrar_liquidacion(pagado=False)
    r = client.get("/api/creditos/juegos/liquidaciones?pagado=false", headers=h).json()["items"]
    assert all(x["pagado"] is False for x in r)


def test_maestro_juegos(client):
    h = _auth(client)
    db = SessionLocal()
    db.add(models.Juego(codigo=1, modalidad=0, cod_afip=73,
                        denominacion="QUINIELA EXPRESS",
                        com_agencia=Decimal("17.50"), com_subagencia=Decimal("12.50")))
    db.commit(); db.close()
    juegos = client.get("/api/creditos/juegos/maestro", headers=h).json()
    qe = next(j for j in juegos if j["denominacion"] == "QUINIELA EXPRESS")
    assert Decimal(qe["com_agencia"]) == Decimal("17.50")
    assert qe["cod_afip"] == 73


def test_sorteos_con_nombre_de_juego(client):
    h = _auth(client)
    import datetime
    db = SessionLocal()
    db.add(models.Juego(codigo=3, modalidad=0, cod_afip=44, denominacion="LOTO TRADICIONAL"))
    db.add(models.Sorteo(cod_juego=3, no_sorteo=1670,
                        fecha_sorteo=datetime.date(2009, 10, 7),
                        fecha_vto=datetime.date(2009, 10, 8), importado_caja=True))
    db.commit(); db.close()
    d = client.get("/api/creditos/juegos/sorteos?cod_juego=3", headers=h).json()
    assert d["total"] >= 1
    s = d["items"][0]
    assert s["no_sorteo"] == 1670
    assert s["juego"] == "LOTO TRADICIONAL"
    assert s["importado_caja"] is True


def test_ingresos_por_juego(client):
    h = _auth(client)
    _sembrar_liquidacion()
    filas = client.get("/api/creditos/juegos/ingresos-por-juego", headers=h).json()
    quiniela = next(f for f in filas if f["juego"] == "QUINIELA")
    assert Decimal(quiniela["recaudacion"]) >= Decimal("100000")
    # neto = recaudación - premios - comisiones (100000 - 60000 - 12000 = 28000)
    assert Decimal(quiniela["neto"]) == (
        Decimal(quiniela["recaudacion"]) - Decimal(quiniela["premios"]) - Decimal(quiniela["comisiones"]))


def _sembrar_agencia_con_deuda(cod_agencia=2504):
    """Dos liquidaciones pendientes de una agencia: una en pesos, otra en bonos."""
    db = SessionLocal()
    db.add(models.LiquidacionAgencia(
        cod_agencia=cod_agencia, no_agencia=801, cod_juego=34, juego="Mi Bingo",
        no_sorteo=14, moneda="$", total=Decimal("66000"), total_gral=Decimal("66000"),
        pagado=False))
    db.add(models.LiquidacionAgencia(
        cod_agencia=cod_agencia, no_agencia=801, cod_juego=10, juego="Quiniela",
        no_sorteo=15, moneda="B", total=Decimal("10000"), total_gral=Decimal("10000"),
        pagado=False))
    db.commit(); db.close()


def test_aplicativo_caja_quiniela_cobro_agencia(client):
    """Aplicativo de Caja (22505 / frm225050000aplicaj): cobra la deuda de una
    agencia con bonos y pesos, calcula vuelto = adeudado - cobrado por moneda,
    graba el recibo (cajapagos) y marca las liquidaciones pagadas."""
    h = _auth(client)
    _sembrar_agencia_con_deuda(cod_agencia=9001)

    # deuda separada por moneda: pesos=66000, bonos=10000
    deuda = client.get("/api/creditos/juegos/agencias/9001/deuda", headers=h).json()
    assert Decimal(deuda["pesos"]) == Decimal("66000.00")
    assert Decimal(deuda["bonos"]) == Decimal("10000.00")
    assert Decimal(deuda["total"]) == Decimal("76000.00")
    assert deuda["cantidad"] == 2

    # RECHAZO de pago parcial: entrega menos que lo adeudado en pesos -> 409 y NO
    # marca nada como pagado (comportamiento real: la cobranza salda el total).
    parcial = client.post("/api/creditos/juegos/agencias/cobrar", headers=h, json={
        "cod_agencia": 9001,
        "formas_pago": [{"moneda": "$", "importe": "30000"},
                        {"moneda": "B", "importe": "10000"}]})
    assert parcial.status_code == 409, parcial.text
    # la deuda sigue intacta
    assert client.get("/api/creditos/juegos/agencias/9001/deuda", headers=h).json()["cantidad"] == 2

    # cobra el total exacto (pesos 66000 + bonos 10000) -> cobrado_total = total, vuelto 0
    r = client.post("/api/creditos/juegos/agencias/cobrar", headers=h, json={
        "cod_agencia": 9001,
        "formas_pago": [{"moneda": "$", "importe": "66000"},
                        {"moneda": "B", "importe": "10000"}]})
    assert r.status_code == 201, r.text
    pago = r.json()
    assert Decimal(pago["cobrado_total"]) == Decimal("76000.00")   # salda el total
    assert Decimal(pago["vuelto_pesos"]) == Decimal("0.00")
    assert Decimal(pago["vuelto_bonos"]) == Decimal("0.00")

    # las liquidaciones quedan pagadas y no hay más deuda
    deuda2 = client.get("/api/creditos/juegos/agencias/9001/deuda", headers=h).json()
    assert deuda2["cantidad"] == 0

    # anular revierte
    an = client.post(f"/api/creditos/juegos/agencias/pagos/{pago['id']}/anular", headers=h).json()
    assert an["anulado"] is True
    deuda3 = client.get("/api/creditos/juegos/agencias/9001/deuda", headers=h).json()
    assert deuda3["cantidad"] == 2


def test_aplicativo_caja_quiniela_sobrepago_da_vuelto(client):
    """Sobrepago: si se entrega más que lo adeudado, se salda el total y el excedente
    queda como vuelto (cambio a devolver)."""
    h = _auth(client)
    _sembrar_agencia_con_deuda(cod_agencia=9002)  # pesos 66000, bonos 10000
    r = client.post("/api/creditos/juegos/agencias/cobrar", headers=h, json={
        "cod_agencia": 9002,
        "formas_pago": [{"moneda": "$", "importe": "70000"},   # 4000 de más
                        {"moneda": "B", "importe": "10000"}]}).json()
    assert Decimal(r["cobrado_total"]) == Decimal("76000.00")  # aplicado = total
    assert Decimal(r["vuelto_pesos"]) == Decimal("4000.00")    # excedente = vuelto
    assert Decimal(r["vuelto_bonos"]) == Decimal("0.00")


def test_informe_deuda_agencia(client):
    """Informe de deuda de agencia (22555): liquidaciones impagas por agencia."""
    h = _auth(client)
    _sembrar_agencia_con_deuda(cod_agencia=9500)
    inf = client.get("/api/creditos/juegos/agencias/deuda-informe?cod_agencia=9500", headers=h).json()
    assert inf["cantidad"] == 2
    assert Decimal(inf["total"]) == Decimal("76000.00")
    assert all("dias_atraso" in it for it in inf["items"])


def test_informe_ingresos_brutos(client):
    """Informe de Ingresos Brutos (23035): agrupa por agencia las liquidaciones
    cobradas en el mes, sumando recaudación, comisiones e ing_brutos."""
    h = _auth(client)
    import datetime
    db = SessionLocal()
    db.add(models.LiquidacionAgencia(
        cod_agencia=5001, no_agencia=10, subagencia=0, juego="Quiniela",
        no_sorteo=1, recaudacion=Decimal("100000"),
        comision_agencia=Decimal("40000"), comision_subagencia=Decimal("0"),
        ing_brutos=Decimal("3500"), total_gral=Decimal("60000"),
        pagado=True, fecha_pago=datetime.date(2025, 8, 12)))
    db.add(models.LiquidacionAgencia(  # otra agencia, mismo mes
        cod_agencia=5002, no_agencia=11, subagencia=0, juego="Loto",
        no_sorteo=2, recaudacion=Decimal("50000"),
        comision_agencia=Decimal("20000"), ing_brutos=Decimal("1750"),
        pagado=True, fecha_pago=datetime.date(2025, 8, 20)))
    db.add(models.LiquidacionAgencia(  # otro mes -> no debe contar
        cod_agencia=5001, no_agencia=10, subagencia=0, juego="Quiniela",
        no_sorteo=3, recaudacion=Decimal("9999"), ing_brutos=Decimal("999"),
        pagado=True, fecha_pago=datetime.date(2025, 9, 1)))
    db.commit(); db.close()

    inf = client.get("/api/creditos/juegos/ingresos-brutos?mes=8&anio=2025", headers=h).json()
    ags = {a["cod_agencia"]: a for a in inf["items"]}
    assert Decimal(ags[5001]["ing_brutos"]) == Decimal("3500.00")
    assert Decimal(ags[5001]["comisiones"]) == Decimal("40000.00")
    assert Decimal(ags[5002]["ing_brutos"]) == Decimal("1750.00")
    assert Decimal(inf["total_ing_brutos"]) == Decimal("5250.00")  # sólo agosto
    assert 5001 in ags and 5002 in ags


def test_liquidaciones_cobradas_en_fecha(client):
    """Liquidaciones cobradas en un día (23050): pagadas con fecha_pago = día, con
    resumen por cajero."""
    h = _auth(client)
    import datetime
    db = SessionLocal()
    db.add(models.LiquidacionAgencia(cod_agencia=1, no_agencia=1, cod_juego=10,
        juego="Quiniela", no_sorteo=1, moneda="$", total_gral=Decimal("5000"),
        pagado=True, no_recibo=100, cajero="ana", fecha_pago=datetime.date(2025, 8, 12)))
    db.add(models.LiquidacionAgencia(cod_agencia=2, no_agencia=2, cod_juego=34,
        juego="Bingo", no_sorteo=2, moneda="$", total_gral=Decimal("3000"),
        pagado=True, no_recibo=101, cajero="ana", fecha_pago=datetime.date(2025, 8, 12)))
    db.add(models.LiquidacionAgencia(cod_agencia=3, no_agencia=3, cod_juego=10,
        juego="Quiniela", no_sorteo=3, total_gral=Decimal("9999"),  # otro día
        pagado=True, no_recibo=102, cajero="ana", fecha_pago=datetime.date(2025, 8, 13)))
    db.commit(); db.close()

    d = client.get("/api/creditos/juegos/liquidaciones-cobradas?fecha=2025-08-12", headers=h).json()
    assert d["cantidad"] == 2
    assert Decimal(d["total"]) == Decimal("8000.00")
    ana = next(r for r in d["resumen"] if r["cajero"] == "ana")
    assert ana["cantidad"] == 2 and Decimal(ana["total"]) == Decimal("8000.00")


def test_premios_quiniela(client):
    """Control de premios (23020): cajaliq con premios != 0, informa la magnitud."""
    h = _auth(client)
    import datetime
    db = SessionLocal()
    # premio cobrado (negativo en base) el 2025-08-12
    db.add(models.LiquidacionAgencia(cod_agencia=1, no_agencia=1, cod_juego=10,
        juego="Quiniela", no_sorteo=1, moneda="$", premios=Decimal("-5000"),
        pagado=True, no_recibo=100, cajero="ana", fecha_pago=datetime.date(2025, 8, 12)))
    # sin premio -> no aparece
    db.add(models.LiquidacionAgencia(cod_agencia=2, no_agencia=2, cod_juego=10,
        juego="Quiniela", no_sorteo=2, premios=Decimal("0"),
        pagado=True, no_recibo=101, cajero="ana", fecha_pago=datetime.date(2025, 8, 12)))
    db.commit(); db.close()

    d = client.get("/api/creditos/juegos/premios?fecha=2025-08-12&modo=cobradas", headers=h).json()
    assert d["cantidad"] == 1
    assert Decimal(d["total"]) == Decimal("5000.00")   # magnitud (abs)
    assert d["items"][0]["premio"] == "5000.00"


def test_cheques_agencias(client):
    """Listado de cheques para agencias (23057): agencias con sum(total_gral) <= -10000
    en una fecha_vto reciben cheque por el neto."""
    h = _auth(client)
    import datetime
    db = SessionLocal()
    # agencia con neto negativo fuerte -> cheque
    db.add(models.LiquidacionAgencia(cod_agencia=100, no_agencia=1, cod_juego=10,
        juego="Q", no_sorteo=1, premios=Decimal("-50000"), total=Decimal("-30000"),
        total_gral=Decimal("-30000"), fecha_vto=datetime.date(2025, 10, 20)))
    # agencia con neto positivo -> no cheque
    db.add(models.LiquidacionAgencia(cod_agencia=101, no_agencia=2, cod_juego=10,
        juego="Q", no_sorteo=2, total=Decimal("5000"), total_gral=Decimal("5000"),
        fecha_vto=datetime.date(2025, 10, 20)))
    # neto negativo pero chico (> -10000) -> no cheque
    db.add(models.LiquidacionAgencia(cod_agencia=102, no_agencia=3, cod_juego=10,
        juego="Q", no_sorteo=3, total=Decimal("-5000"), total_gral=Decimal("-5000"),
        fecha_vto=datetime.date(2025, 10, 20)))
    db.commit(); db.close()

    d = client.get("/api/creditos/juegos/cheques-agencias?fecha_vto=2025-10-20", headers=h).json()
    cods = {i["cod_agencia"]: i for i in d["items"]}
    assert 100 in cods and 101 not in cods and 102 not in cods
    assert Decimal(cods[100]["cheque"]) == Decimal("30000.00")   # -neto
    assert Decimal(d["total_cheques"]) == Decimal("30000.00")


def test_premios_compensados(client):
    """Premios compensados por capital/interior (23055): agrupa cajaliq por interior
    y agencia en una fecha_vto."""
    h = _auth(client)
    import datetime
    db = SessionLocal()
    db.add(models.LiquidacionAgencia(cod_agencia=200, no_agencia=1, cod_juego=10,
        juego="Q", no_sorteo=1, interior=False, total=Decimal("10000"),
        premios=Decimal("-3000"), com_premios=Decimal("300"), total_gral=Decimal("7000"),
        fecha_vto=datetime.date(2025, 10, 20)))
    db.add(models.LiquidacionAgencia(cod_agencia=201, no_agencia=2, cod_juego=10,
        juego="Q", no_sorteo=2, interior=True, total=Decimal("5000"),
        premios=Decimal("-1000"), total_gral=Decimal("4000"),
        fecha_vto=datetime.date(2025, 10, 20)))
    db.commit(); db.close()

    d = client.get("/api/creditos/juegos/premios-compensados?fecha_vto=2025-10-20", headers=h).json()
    g = {x["grupo"]: x for x in d["grupos"]}
    assert Decimal(g["Capital"]["total_gral"]) == Decimal("7000.00")
    assert Decimal(g["Interior"]["total_gral"]) == Decimal("4000.00")
    cap = g["Capital"]["items"][0]
    assert cap["cod_agencia"] == 200 and Decimal(cap["premios"]) == Decimal("3000.00")  # abs
    assert Decimal(d["total_general"]) == Decimal("11000.00")
