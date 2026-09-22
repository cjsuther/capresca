"""
Endpoints internos (contenedor-a-contenedor): API key, encolado de escrituras con
kill switch y lecturas servidas desde el mirror Postgres.
"""
from datetime import date

import pytest

from app.config import settings
from app.models.mirror_caja import (
    MirrorCajacreseg,
    MirrorCajaforpag,
    MirrorCajaliq,
    MirrorCajapagos,
)
from app.models.mirror_creditos import MirrorMaeclientes
from app.models.mirror_juegos import MirrorMaeagencias, MirrorMaejuegos
from app.models.outbox import LegacyOutbox

PAGO = {
    "no_recibo": 5001,
    "cod_agencia": "A01",
    "fecha_pago": "2026-02-09",
    "total": "113400.00",
    "origen": "caja",
    "cajero": "jperez",
    "formas_pago": [{"moneda": "$", "importe": "113400.00", "origen": "efectivo", "sno_recibo": 1}],
    "liquidaciones": [{"cod_agencia": "A01", "cod_juego": 3, "no_sorteo": 77}],
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "legacy"}


def test_el_lifespan_no_levanta_el_scheduler_si_esta_desactivado(monkeypatch):
    from fastapi.testclient import TestClient

    from app import scheduler
    from app.main import app as aplicacion

    monkeypatch.setattr(settings, "sync_enabled", False)
    with TestClient(aplicacion) as c:
        assert c.get("/health").status_code == 200
        assert scheduler._scheduler is None


def test_get_db_entrega_una_sesion_y_la_cierra():
    """La dependencia real (en los tests se reemplaza por la sesión SQLite)."""
    from app.db.session import get_db

    generador = get_db()
    sesion = next(generador)
    assert sesion.is_active
    with pytest.raises(StopIteration):
        next(generador)


@pytest.mark.parametrize("valor,esperado", [(None, None), ("7", 7)])
def test_get_current_user_id(valor, esperado):
    from app.dependencies.auth import get_current_user_id

    assert get_current_user_id(valor) == esperado


def test_get_current_user_id_rechaza_un_header_no_numerico():
    from fastapi import HTTPException

    from app.dependencies.auth import get_current_user_id

    with pytest.raises(HTTPException) as e:
        get_current_user_id("pepe")
    assert e.value.status_code == 401


# ── API key ───────────────────────────────────────────────────────────────────

def test_sin_api_key_no_se_entra(client):
    assert client.get("/internal/legacy/ping").status_code == 422


def test_api_key_invalida_da_401(client):
    r = client.get("/internal/legacy/ping", headers={"X-Api-Key": "otra"})
    assert r.status_code == 401 and r.json()["detail"] == "API key inválida"


def test_api_key_no_configurada_da_503(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "")
    r = client.get("/internal/legacy/ping", headers=auth)
    assert r.status_code == 503 and r.json()["detail"] == "API key no configurada"


def test_ping_expone_el_estado_de_la_integracion(client, auth, share):
    r = client.get("/internal/legacy/ping", headers=auth)
    assert r.status_code == 200
    assert r.json() == {
        "service": "legacy",
        "integration_enabled": True,
        "write_mode": "outbox_only",
        "smb_available": True,
    }


def test_ping_refleja_el_kill_switch(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "integration_enabled", False)
    monkeypatch.setattr(settings, "smb_mount_root", "/ruta/que/no/existe")
    body = client.get("/internal/legacy/ping", headers=auth).json()
    assert body["integration_enabled"] is False and body["smb_available"] is False


# ── Escrituras: siempre al outbox, nunca en caliente ──────────────────────────

def test_aplicar_pago_encola_y_devuelve_202(client, auth, db):
    r = client.post("/internal/legacy/pagos", json=PAGO,
                    headers={**auth, "X-Origin-Module": "cajeros", "X-User-Id": "7"})
    assert r.status_code == 202
    body = r.json()
    assert body["created"] is True and body["status"] == "PENDING"
    assert body["idempotency_key"] == "aplicar_pago:5001"

    fila = db.query(LegacyOutbox).one()
    assert fila.database == "caja" and fila.operation == "aplicar_pago"
    assert fila.origin_module == "cajeros" and fila.origin_user_id == 7
    assert fila.payload["no_recibo"] == 5001 and fila.attempts == 0


def test_aplicar_pago_es_idempotente_por_no_recibo(client, auth, db):
    primero = client.post("/internal/legacy/pagos", json=PAGO, headers=auth).json()
    segundo = client.post("/internal/legacy/pagos", json={**PAGO, "cajero": "otro"},
                          headers=auth).json()
    assert primero["created"] is True and segundo["created"] is False
    assert primero["outbox_id"] == segundo["outbox_id"]
    assert db.query(LegacyOutbox).count() == 1
    # el payload original no se pisa
    assert db.query(LegacyOutbox).one().payload["cajero"] == "jperez"


def test_anular_pago_encola_con_el_no_recibo_de_la_url(client, auth, db):
    r = client.post("/internal/legacy/pagos/5001/anular", json={"motivo": "error de carga"},
                    headers=auth)
    assert r.status_code == 202
    assert r.json()["idempotency_key"] == "anular_pago:5001"
    fila = db.query(LegacyOutbox).one()
    assert fila.payload == {"motivo": "error de carga", "no_recibo": 5001}


def test_consolidar_creditos_es_idempotente_por_fecha(client, auth, db):
    cuerpo = {"fecha": "2026-02-09", "detalle": {"lineas": 3}}
    r1 = client.post("/internal/legacy/creditos/consolidar", json=cuerpo, headers=auth)
    r2 = client.post("/internal/legacy/creditos/consolidar", json=cuerpo, headers=auth)
    assert r1.status_code == 202 and r1.json()["created"] is True
    assert r2.json()["created"] is False
    fila = db.query(LegacyOutbox).one()
    assert fila.database == "creditos"
    assert fila.idempotency_key == "consolidar_creditos:2026-02-09"


def test_payload_invalido_no_llega_al_outbox(client, auth, db):
    assert client.post("/internal/legacy/pagos", json={"cod_agencia": "A01"},
                       headers=auth).status_code == 422
    assert db.query(LegacyOutbox).count() == 0


@pytest.mark.parametrize("metodo,url,cuerpo", [
    ("post", "/internal/legacy/pagos", PAGO),
    ("post", "/internal/legacy/pagos/5001/anular", {"motivo": "x"}),
    ("post", "/internal/legacy/creditos/consolidar", {"fecha": "2026-02-09"}),
])
def test_kill_switch_rechaza_toda_escritura_con_410(client, auth, db, monkeypatch,
                                                    metodo, url, cuerpo):
    monkeypatch.setattr(settings, "integration_enabled", False)
    r = getattr(client, metodo)(url, json=cuerpo, headers=auth)
    assert r.status_code == 410
    assert "INTEGRATION_ENABLED=false" in r.json()["detail"]
    assert db.query(LegacyOutbox).count() == 0


# ── Lecturas: salen del mirror y sobreviven al kill switch ────────────────────

@pytest.fixture
def mirror(db):
    db.add_all([
        MirrorMaeagencias(cod_agencia="A02", titular="Segunda", row_hash="h"),
        MirrorMaeagencias(cod_agencia="A01", titular="Primera", row_hash="h"),
        MirrorMaejuegos(cod_juego=3, descripcion="Quiniela", modalidad=1, row_hash="h"),
        MirrorMaeclientes(cuil="20111111117", nombre="Juan", domicilio="Calle 1", row_hash="h"),
        MirrorMaeclientes(cuil="27222222224", nombre="Ana", domicilio="Calle 2", row_hash="h"),
        MirrorCajaliq(cod_agencia="A01", cod_juego=3, no_sorteo=77, importe="1000.50",
                      intereses="10.25", pagado=False, fecha_pago=None, no_recibo=None,
                      row_hash="h"),
        MirrorCajaliq(cod_agencia="A02", cod_juego=3, no_sorteo=78, importe="200.00",
                      intereses=None, pagado=True, fecha_pago=date(2026, 2, 9),
                      no_recibo=5001, row_hash="h"),
        MirrorCajapagos(no_recibo=5001, cod_agencia="A02", fecha_pago=date(2026, 2, 9),
                        origen="caja", total="200.00", cajero="jperez", row_hash="h"),
        MirrorCajaforpag(no_recibo=5001, sno_recibo=1, moneda="$", origen="efectivo",
                         fecha_pago=date(2026, 2, 9), anulado=False, row_hash="h"),
        MirrorCajacreseg(nrecibo=900, recofi=1, origen="caja", fecha_pago=date(2026, 2, 9),
                         via_pago="caja", usuario_pago="jperez", row_hash="h"),
    ])
    db.commit()


def test_agencias_vienen_ordenadas(client, auth, mirror):
    datos = client.get("/internal/legacy/agencias", headers=auth).json()
    assert [a["cod_agencia"] for a in datos] == ["A01", "A02"]
    assert datos[0]["titular"] == "Primera"


def test_juegos(client, auth, mirror):
    assert client.get("/internal/legacy/juegos", headers=auth).json() == [
        {"cod_juego": 3, "descripcion": "Quiniela", "modalidad": 1}
    ]


def test_maeclientes_filtra_por_cuil(client, auth, mirror):
    assert len(client.get("/internal/legacy/maeclientes", headers=auth).json()) == 2
    datos = client.get("/internal/legacy/maeclientes?cuil=27222222224", headers=auth).json()
    assert [c["nombre"] for c in datos] == ["Ana"]


def test_cajaliq_filtra_por_agencia_y_por_pagado(client, auth, mirror):
    todas = client.get("/internal/legacy/cajaliq", headers=auth).json()
    assert len(todas) == 2
    assert todas[0]["importe"] == 1000.5 and todas[0]["intereses"] == 10.25

    pendientes = client.get("/internal/legacy/cajaliq?pagado=false", headers=auth).json()
    assert [l["no_sorteo"] for l in pendientes] == [77]
    assert pendientes[0]["fecha_pago"] is None

    de_a02 = client.get("/internal/legacy/cajaliq?agencia=A02", headers=auth).json()
    assert de_a02[0]["fecha_pago"] == "2026-02-09" and de_a02[0]["no_recibo"] == 5001


def test_pagos_filtra_por_fecha_y_agencia(client, auth, mirror):
    assert len(client.get("/internal/legacy/pagos", headers=auth).json()) == 1
    assert client.get("/internal/legacy/pagos?fecha=2020-01-01", headers=auth).json() == []
    datos = client.get("/internal/legacy/pagos?fecha=2026-02-09&agencia=A02",
                       headers=auth).json()
    assert datos[0]["no_recibo"] == 5001 and datos[0]["total"] == 200.0


def test_formas_pago_filtra_por_recibo(client, auth, mirror):
    assert client.get("/internal/legacy/formas-pago?no_recibo=999", headers=auth).json() == []
    datos = client.get("/internal/legacy/formas-pago?no_recibo=5001", headers=auth).json()
    assert datos[0]["anulado"] is False and datos[0]["moneda"] == "$"


def test_creditos_seguros_filtra_por_fecha(client, auth, mirror):
    assert client.get("/internal/legacy/creditos-seguros?fecha=2020-01-01",
                      headers=auth).json() == []
    datos = client.get("/internal/legacy/creditos-seguros?fecha=2026-02-09",
                       headers=auth).json()
    assert datos[0]["nrecibo"] == 900 and datos[0]["via_pago"] == "caja"


def test_las_lecturas_siguen_funcionando_con_la_integracion_apagada(client, auth, mirror,
                                                                    monkeypatch):
    """Kill switch: se sirve del mirror, no del legacy."""
    monkeypatch.setattr(settings, "integration_enabled", False)
    assert len(client.get("/internal/legacy/agencias", headers=auth).json()) == 2
    assert len(client.get("/internal/legacy/cajaliq", headers=auth).json()) == 2


# ── Consulta de estado del outbox por el módulo origen ────────────────────────

def test_estado_de_una_operacion_encolada(client, auth):
    oid = client.post("/internal/legacy/pagos", json=PAGO, headers=auth).json()["outbox_id"]
    body = client.get(f"/internal/legacy/outbox/{oid}", headers=auth).json()
    assert body["operation"] == "aplicar_pago" and body["status"] == "PENDING"
    assert body["attempts"] == 0 and body["last_error"] is None
    assert body["applied_at"] is None and body["created_at"] is not None


def test_estado_de_operacion_inexistente_da_404(client, auth):
    assert client.get("/internal/legacy/outbox/999", headers=auth).status_code == 404
