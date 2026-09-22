"""Notificaciones: alta interna (otros módulos), listado, conteo y marcado por usuario."""
from app.models.notification import Notification


def _crear(client, *, user_id=7, titulo="Transacción autorizada", modulo="cajeros", **extra):
    payload = {"notifications": [{"user_id": user_id, "title": titulo,
                                  "message": "Detalle de la novedad", "module": modulo, **extra}]}
    return client.post("/internal/notifications", json=payload)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "notifications"}


def test_alta_interna_crea_las_notificaciones(client, db):
    r = client.post("/internal/notifications", json={"notifications": [
        {"user_id": 7, "title": "Uno", "message": "m", "module": "cajeros",
         "entity_type": "transaction", "entity_id": 5, "redirect_path": "/modules/cajeros",
         "created_by_module": "cajeros"},
        {"user_id": 8, "title": "Dos", "message": "m", "module": "liquidaciones"},
    ]})
    assert r.status_code == 201 and r.json() == {"created": 2}
    assert db.query(Notification).count() == 2
    n = db.query(Notification).filter_by(user_id=7).one()
    assert n.is_read is False and n.read_at is None and n.entity_id == 5


def test_alta_interna_valida_el_payload(client):
    assert client.post("/internal/notifications", json={"notifications": [{"title": "sin user"}]}).status_code == 422


def test_listado_es_por_usuario_y_trae_conteos(client, h):
    _crear(client, user_id=7, titulo="mía")
    _crear(client, user_id=99, titulo="de otro")
    r = client.get("/api/notifications", headers=h).json()
    assert [n["title"] for n in r["data"]] == ["mía"]
    assert r["total"] == 1 and r["unread_count"] == 1


def test_listado_pagina_y_filtra_no_leidas(client, h, db):
    for i in range(3):
        _crear(client, titulo=f"n{i}")
    leida = db.query(Notification).order_by(Notification.id).first()
    client.put(f"/api/notifications/{leida.id}/read", headers=h)

    r = client.get("/api/notifications?limit=2", headers=h).json()
    assert len(r["data"]) == 2 and r["total"] == 3 and r["unread_count"] == 2

    r = client.get("/api/notifications?limit=10&offset=2", headers=h).json()
    assert len(r["data"]) == 1

    r = client.get("/api/notifications?unread_only=true", headers=h).json()
    assert r["total"] == 2 and all(not n["is_read"] for n in r["data"])


def test_unread_count(client, h):
    assert client.get("/api/notifications/unread-count", headers=h).json() == {"count": 0}
    _crear(client)
    assert client.get("/api/notifications/unread-count", headers=h).json() == {"count": 1}


def test_marcar_leida_es_idempotente_y_guarda_la_fecha(client, h, db):
    _crear(client)
    nid = db.query(Notification).one().id
    r1 = client.put(f"/api/notifications/{nid}/read", headers=h).json()
    assert r1["is_read"] is True and r1["read_at"] is not None
    r2 = client.put(f"/api/notifications/{nid}/read", headers=h).json()
    assert r2["read_at"] == r1["read_at"]        # no se pisa la fecha original


def test_no_se_puede_marcar_la_notificacion_de_otro(client, db):
    _crear(client, user_id=99)
    nid = db.query(Notification).one().id
    assert client.put(f"/api/notifications/{nid}/read", headers={"X-User-Id": "7"}).status_code == 404
    assert db.query(Notification).one().is_read is False


def test_marcar_todas_como_leidas_solo_afecta_al_usuario(client, h, db):
    _crear(client, user_id=7)
    _crear(client, user_id=7)
    _crear(client, user_id=99)
    assert client.put("/api/notifications/read-all", headers=h).json() == {"marked": 2}
    assert client.put("/api/notifications/read-all", headers=h).json() == {"marked": 0}
    assert db.query(Notification).filter_by(user_id=99).one().is_read is False


def test_sin_identidad_del_gateway_no_hay_notificaciones(client):
    assert client.get("/api/notifications").status_code == 422          # falta X-User-Id
    assert client.get("/api/notifications", headers={"X-User-Id": "abc"}).status_code == 401
