"""
Router de administración / diagnóstico (/api/legacy): ledger de interacciones,
panel de estado, catálogo de bases, cola del outbox y disparo de sync.
"""
from datetime import date, datetime, timedelta, timezone

from app.config import settings
from app.legacy_catalog import DATABASES
from app.models.interaction_log import LegacyInteractionLog
from app.models.outbox import LegacyOutbox
from app.models.sync_state import LegacySyncState
from app.services.interaction_logger import log_interaction

BASE = "/api/legacy"


def _interaccion(db, **kw):
    datos = {"direction": "IN", "table_name": "cajaliq", "operation": "sync"}
    datos.update(kw)
    return log_interaction(db, **datos)


def _outbox(db, clave, *, status="PENDING", operation="aplicar_pago", database="caja"):
    fila = LegacyOutbox(operation=operation, database=database, idempotency_key=clave,
                        payload={"no_recibo": 1}, status=status)
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


# ── Catálogo ──────────────────────────────────────────────────────────────────

def test_databases_lista_el_catalogo_completo(client):
    assert client.get(f"{BASE}/databases").json() == {"databases": list(DATABASES)}
    assert "contabilidad" in DATABASES


# ── Ledger de interacciones ───────────────────────────────────────────────────

def test_interacciones_vacias(client):
    assert client.get(f"{BASE}/interactions").json() == {
        "total": 0, "page": 1, "page_size": 50, "items": []
    }


def test_la_base_se_infiere_del_catalogo(client, db):
    _interaccion(db, table_name="maeagencias")
    _interaccion(db, table_name="tabla_que_no_existe")
    bases = {i["table_name"]: i["database"]
             for i in client.get(f"{BASE}/interactions").json()["items"]}
    assert bases == {"maeagencias": "juegos", "tabla_que_no_existe": "desconocida"}


def test_interacciones_se_devuelven_de_la_mas_nueva_a_la_mas_vieja(client, db):
    for i in range(3):
        _interaccion(db, operation=f"op{i}")
    items = client.get(f"{BASE}/interactions").json()["items"]
    assert [i["operation"] for i in items] == ["op2", "op1", "op0"]


def test_interacciones_filtran_por_direccion_base_tabla_y_estado(client, db):
    _interaccion(db, direction="IN", table_name="cajaliq", status="OK")
    _interaccion(db, direction="OUT", table_name="cajapagos", status="ERROR",
                 error_message="boom", outbox_id=42, rows_affected=0)
    _interaccion(db, direction="IN", table_name="maeclientes", status="OK")

    assert client.get(f"{BASE}/interactions?direction=OUT").json()["total"] == 1
    assert client.get(f"{BASE}/interactions?database=caja").json()["total"] == 2
    assert client.get(f"{BASE}/interactions?table=maeclientes").json()["total"] == 1
    assert client.get(f"{BASE}/interactions?status=ERROR").json()["total"] == 1

    err = client.get(f"{BASE}/interactions?status=ERROR").json()["items"][0]
    assert err["error_message"] == "boom" and err["outbox_id"] == 42


def test_interacciones_filtran_por_rango_de_fechas(client, db):
    vieja = _interaccion(db, operation="vieja")
    ayer = datetime.now(timezone.utc) - timedelta(days=1)
    vieja.occurred_at = ayer
    vieja.occurred_date = ayer.date()
    db.commit()
    _interaccion(db, operation="hoy")

    hoy = date.today().isoformat()
    assert client.get(f"{BASE}/interactions?date_from={hoy}").json()["total"] == 1
    assert client.get(f"{BASE}/interactions?date_to={ayer.date()}").json()["total"] == 1
    assert client.get(f"{BASE}/interactions?date_from={ayer.date()}&date_to={hoy}"
                      ).json()["total"] == 2


def test_interacciones_paginan(client, db):
    for i in range(5):
        _interaccion(db, operation=f"op{i}")
    r = client.get(f"{BASE}/interactions?page=2&page_size=2").json()
    assert r["total"] == 5 and r["page"] == 2 and len(r["items"]) == 2
    assert [i["operation"] for i in r["items"]] == ["op2", "op1"]


def test_interacciones_validan_los_filtros(client):
    r = client.get(f"{BASE}/interactions?database=inexistente")
    assert r.status_code == 400 and "inexistente" in r.json()["detail"]
    assert client.get(f"{BASE}/interactions?direction=ARRIBA").status_code == 400
    assert client.get(f"{BASE}/interactions?page=0").status_code == 422
    assert client.get(f"{BASE}/interactions?page_size=501").status_code == 422


def test_detalle_de_una_interaccion(client, db):
    entrada = _interaccion(db, rows_affected=12, latency_ms=34,
                           payload_summary={"rows_seen": 12})
    body = client.get(f"{BASE}/interactions/{entrada.id}").json()
    assert body["rows_affected"] == 12 and body["latency_ms"] == 34
    assert body["payload_summary"] == {"rows_seen": 12}


def test_detalle_inexistente_da_404(client):
    assert client.get(f"{BASE}/interactions/999").status_code == 404


# ── Panel de estado ───────────────────────────────────────────────────────────

def test_status_refleja_configuracion_sync_y_outbox(client, db, share):
    db.add(LegacySyncState(table_name="cajaliq", database="caja", last_status="OK",
                           rows_seen=10, rows_changed=2, watermark="5001"))
    db.commit()
    _outbox(db, "a", status="PENDING")
    _outbox(db, "b", status="DRAINING")
    _outbox(db, "c", status="APPLIED")     # no cuenta como pendiente

    body = client.get(f"{BASE}/status").json()
    assert body["integration_enabled"] is True and body["write_mode"] == "outbox_only"
    assert body["outbox_pending"] == 2
    assert body["sync_state"][0]["table_name"] == "cajaliq"
    assert body["sync_state"][0]["watermark"] == "5001"
    assert body["smb"]["mounted"] is True and body["smb"]["mount_root"] == str(share)


def test_status_avisa_cuando_el_share_no_esta_montado(client, monkeypatch):
    monkeypatch.setattr(settings, "smb_mount_root", "/ruta/inexistente")
    monkeypatch.setattr(settings, "integration_enabled", False)
    body = client.get(f"{BASE}/status").json()
    assert body["integration_enabled"] is False
    assert body["smb"]["mounted"] is False and "no está accesible" in body["smb"]["error"]
    assert body["outbox_pending"] == 0 and body["sync_state"] == []


# ── Cola del outbox ───────────────────────────────────────────────────────────

def test_outbox_lista_filtra_por_estado_y_pagina(client, db):
    _outbox(db, "a", status="PENDING")
    _outbox(db, "b", status="APPLIED")
    _outbox(db, "c", status="PENDING")

    todas = client.get(f"{BASE}/outbox").json()
    assert todas["total"] == 3 and len(todas["items"]) == 3
    assert todas["items"][0]["payload"] == {"no_recibo": 1}

    pendientes = client.get(f"{BASE}/outbox?status=PENDING").json()
    assert pendientes["total"] == 2
    assert {i["idempotency_key"] for i in pendientes["items"]} == {"a", "c"}

    pagina = client.get(f"{BASE}/outbox?page=2&page_size=2").json()
    assert pagina["total"] == 3 and len(pagina["items"]) == 1


# ── Drenado ───────────────────────────────────────────────────────────────────

def test_drain_dry_run_no_cambia_el_outbox_pero_deja_traza(client, db):
    fila = _outbox(db, "aplicar_pago:1")
    body = client.post(f"{BASE}/outbox/drain").json()

    assert body["mode"] == "dry_run" and body["applied"] == 0 and body["would_apply"] == 1
    assert body["entries"][0] == {
        "outbox_id": fila.id, "operation": "aplicar_pago", "database": "caja",
        "table": "cajapagos", "idempotency_key": "aplicar_pago:1",
    }
    db.expire_all()
    assert db.query(LegacyOutbox).one().status == "PENDING"

    traza = db.query(LegacyInteractionLog).one()
    assert traza.direction == "OUT" and traza.outbox_id == fila.id
    assert traza.payload_summary == {"dry_run": True, "idempotency_key": "aplicar_pago:1"}


def test_drain_dry_run_usa_la_operacion_como_tabla_si_no_la_conoce(client, db):
    _outbox(db, "x", operation="operacion_rara", database="general")
    entrada = client.post(f"{BASE}/outbox/drain").json()["entries"][0]
    assert entrada["database"] == "general" and entrada["table"] == "operacion_rara"


def test_drain_dry_run_ignora_las_que_no_estan_pendientes(client, db):
    _outbox(db, "a", status="APPLIED")
    _outbox(db, "b", status="FAILED")
    assert client.post(f"{BASE}/outbox/drain").json()["would_apply"] == 0


def test_drain_real_esta_bloqueado_por_defecto(client, db):
    _outbox(db, "aplicar_pago:1")
    r = client.post(f"{BASE}/outbox/drain?mode=real")
    assert r.status_code == 409 and "ALLOW_REAL_DRAIN=false" in r.json()["detail"]
    db.expire_all()
    assert db.query(LegacyOutbox).one().status == "PENDING"


def test_drain_solo_acepta_los_modos_conocidos(client):
    assert client.post(f"{BASE}/outbox/drain?mode=produccion").status_code == 422


def test_drain_notifica_solo_si_hay_usuario(client, db, notificaciones):
    _outbox(db, "aplicar_pago:1")
    client.post(f"{BASE}/outbox/drain")
    assert notificaciones == []

    client.post(f"{BASE}/outbox/drain", headers={"X-User-Id": "7"})
    assert len(notificaciones) == 1
    aviso = notificaciones[0]
    assert aviso["user_id"] == 7 and aviso["module"] == "legacy"
    assert "0 aplicado(s), 1 pendiente(s), 0 con error" in aviso["message"]


# ── Sync on-demand ────────────────────────────────────────────────────────────

def test_sync_rechaza_tablas_no_sincronizables(client):
    r = client.post(f"{BASE}/sync/solble")
    assert r.status_code == 404 and "solble" in r.json()["detail"]


def test_sync_esta_apagado_por_el_kill_switch(client, monkeypatch):
    monkeypatch.setattr(settings, "integration_enabled", False)
    r = client.post(f"{BASE}/sync/maeagencias")
    assert r.status_code == 410 and "INTEGRATION_ENABLED=false" in r.json()["detail"]


def test_sync_on_demand_espeja_la_dbf_y_notifica(client, db, share, notificaciones, escribir_dbf):
    escribir_dbf(share, "maeagencias", [
        {"COD_AGEN": "A01", "TITULAR": "Primera"},
        {"COD_AGEN": "A02", "TITULAR": "Segunda"},
    ])
    body = client.post(f"{BASE}/sync/maeagencias", headers={"X-User-Id": "7"}).json()
    assert body == {"table": "maeagencias", "status": "OK", "rows_seen": 2, "rows_changed": 2}
    assert notificaciones[0]["entity_type"] == "sync"
    assert "2 fila(s)" in notificaciones[0]["message"]

    estado = client.get(f"{BASE}/status").json()["sync_state"][0]
    assert estado["last_status"] == "OK" and estado["rows_changed"] == 2


def test_sync_de_una_dbf_ausente_queda_en_error_sin_romper(client, share):
    body = client.post(f"{BASE}/sync/maejuegos").json()
    assert body["status"] == "ERROR" and "No se encontró la DBF" in body["error"]
