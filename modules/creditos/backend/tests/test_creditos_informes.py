"""Informes/consultas de Créditos: solicitudes activas, listado, mora, saldos."""
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


def _otorgar(client, h, monto="180000", cuotas=6, vto="2026-02-10"):
    cli = client.get("/api/creditos/clientes", headers=h).json()["items"][0]["id"]
    lineas = client.get("/api/creditos/creditos/lineas", headers=h).json()
    linea = next(l for l in lineas if l["tipo_calculo"] == 1)
    s = client.post("/api/creditos/creditos/solicitudes", headers=h, json={
        "cliente_id": cli, "linea_id": linea["id"], "monto_solicitado": monto,
        "cantidad_cuotas": cuotas, "fecha_primer_vencimiento": vto}).json()
    return client.post(f"/api/creditos/creditos/solicitudes/{s['id']}/otorgar", headers=h).json()


def test_turnos_otorgados(client):
    h = _auth(client)
    import datetime
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    db.add(models.TurnoCredito(tipo="TODO", numero=1, periodo="012016",
        fecha=datetime.date(2016, 3, 8), cuil="27251174364",
        apellido_nombre="FERREYRA, EDA YAMILE", linea=8050,
        sueldo=Decimal("14000"), usado=True, autorizado=True))
    db.commit(); db.close()
    r = client.get("/api/creditos/creditos/consultas/turnos?periodo=012016", headers=h).json()
    assert r["total"] >= 1
    t = r["items"][0]
    assert t["apellido_nombre"] == "FERREYRA, EDA YAMILE"
    assert t["usado"] is True
    # filtro por usado + búsqueda
    r2 = client.get("/api/creditos/creditos/consultas/turnos?q=FERREYRA&usado=true", headers=h).json()
    assert r2["total"] == 1
    # export a Excel
    x = client.get("/api/creditos/creditos/consultas/turnos/excel?periodo=012016", headers=h)
    assert x.status_code == 200 and x.content[:2] == b"PK"


def test_situacion_por_cartera(client):
    h = _auth(client)
    _otorgar(client, h)  # otorga un crédito en una línea con cartera
    r = client.get("/api/creditos/creditos/consultas/por-cartera", headers=h).json()
    assert r["por_cartera"]
    assert r["total"]["activos"] >= 1
    # cada fila tiene nombre de cartera y saldo
    fila = r["por_cartera"][0]
    assert "nombre" in fila and "saldo" in fila
    # export a PDF
    pdf = client.get("/api/creditos/creditos/consultas/por-cartera/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_detalle_credito_migrado_sin_solicitud(client):
    # Regresión: un crédito del ETL (solicitud_id=None, sin cuotas) no debe dar 500.
    h = _auth(client)
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    cli = models.Cliente(id=9101, id_cliente="MIGRA00000001", apellido_nombre="MIGRADO TEST",
                         cuil="20999999911", dni="99999911", sueldo=Decimal("100000"))
    db.add(cli); db.flush()
    cr = models.Credito(cliente_id=cli.id, solicitud_id=None, linea_id=None,
                        capital=Decimal("50000"), saldo_capital=Decimal("50000"), estado="A")
    db.add(cr); db.commit(); cid = cr.id; db.close()
    r = client.get(f"/api/creditos/creditos/{cid}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["solicitud_id"] is None
    assert body["cantidad_cuotas"] == 0


def test_pagos_en_caja(client):
    h = _auth(client)
    import datetime
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    cli = models.Cliente(id=9102, id_cliente="PAGOCAJA00001", apellido_nombre="PAGA TEST",
                         cuil="20999999988", dni="99999988", sueldo=Decimal("100000"))
    db.add(cli); db.flush()
    cr = models.Credito(cliente_id=cli.id, capital=Decimal("60000"),
                        saldo_capital=Decimal("0"), estado="C")
    db.add(cr); db.flush()
    db.add(models.Cuota(credito_id=cr.id, numero=1, fecha_vencimiento=datetime.date(2026, 3, 10),
        saldo_capital=Decimal("0"), amortizacion=Decimal("60000"), interes=Decimal("0"),
        iva_interes=Decimal("0"), seguro=Decimal("0"), iva_seguro=Decimal("0"),
        gastos_adm=Decimal("0"), iva_gastos_adm=Decimal("0"), total=Decimal("60000"),
        total_pagado=Decimal("60000"), estado="P",
        fecha_pago=datetime.date(2026, 3, 5), nro_recibo=555, via_pago="EFEC",
        usuario_pago="cajero1"))
    db.commit(); db.close()

    r = client.get("/api/creditos/creditos/consultas/pagos-caja?desde=2026-03-01&hasta=2026-03-31", headers=h).json()
    assert r["total"] >= 1
    pago = next(i for i in r["items"] if i["nro_recibo"] == 555)
    assert pago["cajero"] == "cajero1"
    assert Decimal(pago["total_pagado"]) == Decimal("60000")
    assert Decimal(r["total_pagado"]) >= Decimal("60000")
    # export a Excel
    x = client.get("/api/creditos/creditos/consultas/pagos-caja/excel?desde=2026-03-01&hasta=2026-03-31", headers=h)
    assert x.status_code == 200 and x.content[:2] == b"PK"


def test_creditos_sin_debito(client):
    h = _auth(client)
    from app.core.database import SessionLocal
    from app import models
    db = SessionLocal()
    cli = models.Cliente(id=9103, id_cliente="SINCBU0000001", apellido_nombre="SIN CBU TEST",
                         cuil="20999999997", dni="99999999",
                         sueldo=Decimal("100000"), cbu="")
    db.add(cli); db.flush()
    db.add(models.Credito(cliente_id=cli.id, capital=Decimal("50000"),
                          saldo_capital=Decimal("50000"), estado="A"))
    db.commit(); cid = cli.id; db.close()

    r = client.get("/api/creditos/creditos/consultas/sin-debito", headers=h).json()
    assert r["total"] >= 1
    assert any(i["cliente"] == "SIN CBU TEST" for i in r["items"])
    # búsqueda por CUIL
    r2 = client.get("/api/creditos/creditos/consultas/sin-debito?q=20999999997", headers=h).json()
    assert r2["total"] == 1
    # filtro por línea inexistente -> 0 (variante "Línea 25")
    r3 = client.get("/api/creditos/creditos/consultas/sin-debito?linea_id=999999", headers=h).json()
    assert r3["total"] == 0


def test_informe_creditos_filtros(client):
    h = _auth(client)
    cred = _otorgar(client, h)
    linea = client.get(f"/api/creditos/creditos/{cred['id']}", headers=h).json()["linea_id"]
    # filtro por línea + con_saldo=true
    r = client.get(f"/api/creditos/creditos/consultas/creditos?linea_id={linea}&con_saldo=true", headers=h).json()
    assert r["total"] >= 1
    assert all(Decimal(i["saldo"]) > 0 for i in r["items"])
    # filtro por estado inexistente -> 0
    r2 = client.get("/api/creditos/creditos/consultas/creditos?estado=C&linea_id=" + str(linea), headers=h).json()
    assert r2["total"] == 0
    # excel con filtros
    x = client.get(f"/api/creditos/creditos/consultas/creditos/excel?linea_id={linea}", headers=h)
    assert x.status_code == 200 and x.content[:2] == b"PK"


def test_listado_creditos_y_saldos(client):
    h = _auth(client)
    cred = _otorgar(client, h)
    r = client.get("/api/creditos/creditos/consultas/creditos", headers=h).json()
    assert r["cantidad"] >= 1
    assert Decimal(r["total_saldo"]) >= Decimal("180000")
    assert any(i["credito_id"] == cred["id"] for i in r["items"])
    # filtro por estado activo
    r2 = client.get("/api/creditos/creditos/consultas/creditos?estado=A", headers=h).json()
    assert all(i["estado"] == "A" for i in r2["items"])


def test_listado_creditos_excel(client):
    h = _auth(client)
    _otorgar(client, h)
    r = client.get("/api/creditos/creditos/consultas/creditos/excel", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    # los .xlsx son zips: empiezan con 'PK'
    assert r.content[:2] == b"PK"
    assert len(r.content) > 0


def test_cuotas_en_mora(client):
    h = _auth(client)
    _otorgar(client, h, vto="2026-02-10")
    # a fin de año, todas las cuotas están vencidas
    r = client.get("/api/creditos/creditos/consultas/cuotas-mora?fecha_corte=2026-12-31", headers=h).json()
    assert r["cantidad"] >= 1
    assert all(i["dias_mora"] > 0 for i in r["items"])
    assert Decimal(r["total"]) > 0
