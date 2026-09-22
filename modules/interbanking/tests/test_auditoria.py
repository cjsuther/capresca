"""Log de auditoría: toda llamada al proveedor queda registrada, se lista con
filtros, se exporta a CSV y se consulta por id."""
from datetime import datetime, timedelta, timezone

from app.services import audit_service

BASE = "/api/interbanking/auditoria"


def _log(db, **kw):
    datos = dict(user_id=7, operation="LISTAR_CUENTAS", method="GET",
                 endpoint="/v1/accounts", request_payload=None, response_status=200,
                 response_payload={"accounts": []}, duration_ms=12, success=True)
    datos.update(kw)
    return audit_service.log(db=db, **datos)


def test_el_registro_guarda_todos_los_campos(db):
    entrada = _log(db, username="cris", credential_id=None, ip_address="200.1.2.3",
                   request_payload={"a": 1})

    assert entrada.id is not None
    assert entrada.created_at is not None
    assert entrada.request_payload == {"a": 1}       # JSONB round-trip
    assert entrada.response_payload == {"accounts": []}


def test_listado_vacio(client):
    assert client.get(BASE).json() == {"data": [], "total": 0, "page": 1, "per_page": 50}


def test_listado_ordena_por_fecha_descendente(client, db):
    for i in range(3):
        entrada = _log(db, operation=f"OP{i}")
        entrada.created_at = datetime(2026, 3, 10 + i, 12, 0, tzinfo=timezone.utc)
    db.commit()

    filas = client.get(BASE).json()["data"]

    assert [f["operation"] for f in filas] == ["OP2", "OP1", "OP0"]


def test_listado_pagina(client, db):
    for i in range(5):
        _log(db, operation=f"OP{i}")

    r = client.get(f"{BASE}?page=1&per_page=2").json()
    assert len(r["data"]) == 2 and r["total"] == 5

    r = client.get(f"{BASE}?page=3&per_page=2").json()
    assert len(r["data"]) == 1 and r["page"] == 3


def test_listado_filtra_por_operacion_usuario_y_exito(client, db):
    _log(db, operation="LISTAR_CUENTAS", user_id=7, success=True)
    _log(db, operation="CREAR_TRANSFERENCIA", user_id=7, success=False,
         error_message="rechazada")
    _log(db, operation="LISTAR_CUENTAS", user_id=99, success=True)

    assert client.get(f"{BASE}?operation=LISTAR_CUENTAS").json()["total"] == 2
    assert client.get(f"{BASE}?user_id=99").json()["total"] == 1
    assert client.get(f"{BASE}?success=false").json()["total"] == 1

    fallida = client.get(f"{BASE}?success=false").json()["data"][0]
    assert fallida["error_message"] == "rechazada"


def test_listado_filtra_por_rango_de_fechas(client, db):
    _log(db, operation="HOY")
    hoy = datetime.now(timezone.utc).date()
    ayer = (hoy - timedelta(days=1)).isoformat()
    manana = (hoy + timedelta(days=1)).isoformat()

    assert client.get(f"{BASE}?date_from={ayer}&date_to={manana}").json()["total"] == 1
    assert client.get(f"{BASE}?date_from={manana}").json()["total"] == 0
    assert client.get(f"{BASE}?date_to={ayer}").json()["total"] == 0


def test_listado_valida_la_paginacion(client):
    assert client.get(f"{BASE}?page=0").status_code == 422
    assert client.get(f"{BASE}?per_page=500").status_code == 422


def test_detalle_por_id(client, db):
    entrada = _log(db, username="cris", ip_address="10.0.0.9")

    r = client.get(f"{BASE}/{entrada.id}").json()

    assert r["id"] == entrada.id and r["username"] == "cris"
    assert r["ip_address"] == "10.0.0.9" and r["duration_ms"] == 12


def test_detalle_inexistente_es_404(client):
    r = client.get(f"{BASE}/99999")
    assert r.status_code == 404 and r.json()["detail"] == "Registro no encontrado"


def test_export_csv(client, db):
    _log(db, operation="LISTAR_CUENTAS", username="cris", ip_address="10.0.0.9")
    _log(db, operation="CREAR_TRANSFERENCIA", success=False, error_message="boom")

    r = client.get(f"{BASE}/export")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=auditoria.csv" in r.headers["content-disposition"]
    lineas = r.text.strip().splitlines()
    assert lineas[0].startswith("id,created_at,user_id,username,operation")
    assert len(lineas) == 3
    assert "LISTAR_CUENTAS" in r.text and "boom" in r.text


def test_export_csv_respeta_los_filtros(client, db):
    _log(db, operation="LISTAR_CUENTAS")
    _log(db, operation="CREAR_TRANSFERENCIA")

    r = client.get(f"{BASE}/export?operation=CREAR_TRANSFERENCIA")

    assert len(r.text.strip().splitlines()) == 2
    assert "LISTAR_CUENTAS" not in r.text


def test_la_auditoria_refleja_una_operacion_real_de_punta_a_punta(client, db, cred, red, h):
    red.token()
    red.ruta("/v1/accounts", body={"accounts": []})

    client.get("/api/interbanking/cuentas", headers=h)

    operaciones = [f["operation"] for f in client.get(BASE).json()["data"]]
    assert sorted(operaciones) == ["LISTAR_CUENTAS", "OBTENER_TOKEN[info-financiera]"]
