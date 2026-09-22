"""Solicitudes de autorización, relaciones cajero/autorizador, límites y operaciones.

Estos routers existen en el módulo pero main.py no los monta (ver informe): se prueban
contra la app auxiliar `client_extra`, que los expone con el mismo prefijo.
"""
from app.models.limit import UserLimit
from app.models.relation import AuthorizationRelation
from app.models.request import AuthorizationRequest, RequestStatus

REQ = "/api/cajeros/requests"
REL = "/api/cajeros/relations"
LIM = "/api/cajeros/limits"
OPS = "/api/cajeros/operations"


def relacion(db, *, cajero=7, autorizador=20, umbral="0", currency="ARS", activa=True):
    rel = AuthorizationRelation(cajero_user_id=cajero, authorizer_user_id=autorizador,
                                amount_threshold=umbral, currency=currency, is_active=activa)
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


# --- relaciones -------------------------------------------------------------------

def test_alta_de_relacion(client_extra, h, db):
    r = client_extra.post(REL, json={"cajero_user_id": 7, "authorizer_user_id": 20,
                                     "amount_threshold": "5000", "currency": "ARS"}, headers=h)
    assert r.status_code == 201
    assert r.json()["amount_threshold"] == "5000.00"
    assert db.query(AuthorizationRelation).count() == 1


def test_no_se_repite_el_mismo_umbral_para_un_cajero(client_extra, h, db):
    relacion(db, umbral="5000")
    r = client_extra.post(REL, json={"cajero_user_id": 7, "authorizer_user_id": 21,
                                     "amount_threshold": "5000", "currency": "ARS"}, headers=h)
    assert r.status_code == 400 and "umbral" in r.json()["detail"]
    # Otro umbral o otra moneda sí entran.
    assert client_extra.post(REL, json={"cajero_user_id": 7, "authorizer_user_id": 21,
                                        "amount_threshold": "9000"}, headers=h).status_code == 201
    assert client_extra.post(REL, json={"cajero_user_id": 7, "authorizer_user_id": 21,
                                        "amount_threshold": "5000",
                                        "currency": "USD"}, headers=h).status_code == 201


def test_listado_de_relaciones_trae_las_de_cajero_y_autorizador(client_extra, h, h_auth, db):
    relacion(db, cajero=7, autorizador=20)
    relacion(db, cajero=8, autorizador=21, umbral="1")
    relacion(db, cajero=7, autorizador=20, umbral="2", activa=False)

    assert len(client_extra.get(REL, headers=h).json()) == 1       # como cajero
    assert len(client_extra.get(REL, headers=h_auth).json()) == 1  # como autorizador
    assert client_extra.get(REL, headers={"X-User-Id": "99"}).json() == []


def test_baja_de_relacion_solo_para_los_involucrados(client_extra, h, db):
    rel = relacion(db)
    assert client_extra.delete(f"{REL}/999", headers=h).status_code == 404
    assert client_extra.delete(f"{REL}/{rel.id}", headers={"X-User-Id": "99"}).status_code == 403
    assert client_extra.delete(f"{REL}/{rel.id}", headers=h).status_code == 204
    db.expire_all()
    assert db.query(AuthorizationRelation).filter_by(id=rel.id).one().is_active is False


# --- solicitudes ------------------------------------------------------------------

def test_solicitud_sin_relacion_queda_sin_autorizador(client_extra, h):
    r = client_extra.post(REQ, json={"amount": "100", "reason": "adelanto"}, headers=h)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["status"] == "PENDING" and cuerpo["authorizer_user_id"] is None
    assert cuerpo["cajero_user_id"] == 7


def test_la_solicitud_toma_el_umbral_mas_alto_que_aplica(client_extra, h, db):
    relacion(db, autorizador=20, umbral="0")
    relacion(db, autorizador=21, umbral="10000")

    assert client_extra.post(REQ, json={"amount": "500"}, headers=h).json()["authorizer_user_id"] == 20
    assert client_extra.post(REQ, json={"amount": "50000"}, headers=h).json()["authorizer_user_id"] == 21
    # Otra moneda: ninguna relación aplica.
    assert client_extra.post(REQ, json={"amount": "50000", "currency": "USD"},
                             headers=h).json()["authorizer_user_id"] is None


def test_listado_de_solicitudes_por_rol(client_extra, h, h_auth, db):
    relacion(db)
    client_extra.post(REQ, json={"amount": "100"}, headers=h)
    client_extra.post(REQ, json={"amount": "200"}, headers={"X-User-Id": "8"})

    mias = client_extra.get(REQ, headers=h).json()
    assert [x["cajero_user_id"] for x in mias] == [7]
    assert client_extra.get(REQ, headers=h_auth).json() == []

    a_autorizar = client_extra.get(f"{REQ}?as_authorizer=true", headers=h_auth).json()
    assert [x["cajero_user_id"] for x in a_autorizar] == [7]


def test_detalle_de_solicitud_y_404(client_extra, h, db):
    req_id = client_extra.post(REQ, json={"amount": "100"}, headers=h).json()["id"]
    assert client_extra.get(f"{REQ}/{req_id}", headers=h).json()["id"] == req_id
    r = client_extra.get(f"{REQ}/999", headers=h)
    assert r.status_code == 404 and r.json()["detail"] == "Solicitud no encontrada"


def test_aprobar_crea_la_operacion_autorizada(client_extra, h, h_auth, db):
    relacion(db)
    req_id = client_extra.post(REQ, json={"amount": "750"}, headers=h).json()["id"]

    r = client_extra.put(f"{REQ}/{req_id}/approve", json={"resolution_notes": "ok"}, headers=h_auth)
    cuerpo = r.json()
    assert cuerpo["status"] == "APPROVED" and cuerpo["authorizer_user_id"] == 20
    assert cuerpo["resolved_at"] is not None and cuerpo["resolution_notes"] == "ok"

    ops = client_extra.get(OPS, headers=h).json()
    assert len(ops) == 1
    assert ops[0]["request_id"] == req_id and ops[0]["amount"] == "750.00"
    assert ops[0]["executed_by_user_id"] == 20 and ops[0]["notes"] == "ok"


def test_rechazar_no_crea_operacion(client_extra, h, h_auth, db):
    relacion(db)
    req_id = client_extra.post(REQ, json={"amount": "100"}, headers=h).json()["id"]
    cuerpo = client_extra.put(f"{REQ}/{req_id}/reject", json={"resolution_notes": "sin cupo"},
                              headers=h_auth).json()
    assert cuerpo["status"] == "REJECTED" and cuerpo["resolution_notes"] == "sin cupo"
    assert client_extra.get(OPS, headers=h).json() == []


def test_solo_el_autorizador_asignado_resuelve(client_extra, h, db):
    relacion(db)
    req_id = client_extra.post(REQ, json={"amount": "100"}, headers=h).json()["id"]
    ajeno = {"X-User-Id": "99"}
    assert client_extra.put(f"{REQ}/{req_id}/approve", json={}, headers=ajeno).status_code == 403
    assert client_extra.put(f"{REQ}/{req_id}/reject", json={}, headers=ajeno).status_code == 403


def test_una_solicitud_sin_autorizador_la_resuelve_cualquiera(client_extra, h, db):
    # Sin relación no hay autorizador asignado y la guarda `if req.authorizer_user_id`
    # (app/services/request_service.py:70) no corta: la toma quien la resuelva.
    req_id = client_extra.post(REQ, json={"amount": "100"}, headers=h).json()["id"]
    cuerpo = client_extra.put(f"{REQ}/{req_id}/approve", json={}, headers={"X-User-Id": "99"}).json()
    assert cuerpo["status"] == "APPROVED" and cuerpo["authorizer_user_id"] == 99


def test_no_se_resuelve_dos_veces(client_extra, h, h_auth, db):
    relacion(db)
    req_id = client_extra.post(REQ, json={"amount": "100"}, headers=h).json()["id"]
    client_extra.put(f"{REQ}/{req_id}/approve", json={}, headers=h_auth)

    r = client_extra.put(f"{REQ}/{req_id}/approve", json={}, headers=h_auth)
    assert r.status_code == 400 and "PENDING" in r.json()["detail"]
    r = client_extra.put(f"{REQ}/{req_id}/reject", json={}, headers=h_auth)
    assert r.status_code == 400 and "PENDING" in r.json()["detail"]
    assert db.query(AuthorizationRequest).filter_by(id=req_id).one().status == RequestStatus.APPROVED


def test_aprobar_o_rechazar_inexistente_da_404(client_extra, h_auth):
    assert client_extra.put(f"{REQ}/999/approve", json={}, headers=h_auth).status_code == 404
    assert client_extra.put(f"{REQ}/999/reject", json={}, headers=h_auth).status_code == 404


def test_pendientes_del_autorizador(client_extra, h, h_auth, db):
    from app.services.request_service import get_all_pending
    relacion(db)
    client_extra.post(REQ, json={"amount": "100"}, headers=h)
    resuelta = client_extra.post(REQ, json={"amount": "200"}, headers=h).json()["id"]
    client_extra.put(f"{REQ}/{resuelta}/reject", json={}, headers=h_auth)

    assert len(get_all_pending(db, 20)) == 1
    assert get_all_pending(db, 99) == []


# --- límites ----------------------------------------------------------------------

def test_el_limite_propio_se_crea_en_cero_la_primera_vez(client_extra, h, db):
    cuerpo = client_extra.get(LIM, headers=h).json()
    assert cuerpo["user_id"] == 7
    assert cuerpo["daily_limit"] == "0.00" and cuerpo["per_transaction_limit"] == "0.00"
    assert cuerpo["currency"] == "ARS" and cuerpo["is_active"] is True
    # Idempotente: no duplica la fila.
    client_extra.get(LIM, headers=h)
    assert db.query(UserLimit).filter_by(user_id=7).count() == 1


def test_consultar_el_limite_de_otro_usuario(client_extra, h, db):
    assert client_extra.get(f"{LIM}/42", headers=h).json()["user_id"] == 42
    assert db.query(UserLimit).filter_by(user_id=42).count() == 1


def test_actualizar_limite_aplica_solo_los_campos_enviados(client_extra, h, db):
    client_extra.put(f"{LIM}/7", json={"daily_limit": "50000", "currency": "USD"}, headers=h)
    cuerpo = client_extra.put(f"{LIM}/7", json={"per_transaction_limit": "1000"}, headers=h).json()
    assert cuerpo["daily_limit"] == "50000.00"       # se conserva
    assert cuerpo["per_transaction_limit"] == "1000.00"
    assert cuerpo["currency"] == "USD"

    apagado = client_extra.put(f"{LIM}/7", json={"is_active": False}, headers=h).json()
    assert apagado["is_active"] is False


def test_cualquiera_puede_cambiar_el_limite_de_otro(client_extra, db):
    # TODO(bug): PUT /limits/{id} no pide identidad ni permisos
    # (app/routers/limits.py:22-24): no hay control de quién edita el límite de quién.
    r = client_extra.put(f"{LIM}/42", json={"daily_limit": "999999"}, headers={})
    assert r.status_code == 200 and r.json()["daily_limit"] == "999999.00"
