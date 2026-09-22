"""Transacciones: evaluación de reglas al crear, visibilidad y transiciones de estado."""
from app.models.authorization_rule import AuthorizationRule
from app.models.transaction import Transaction, TransactionRuleTrigger

BASE = "/api/cajeros/transactions"
RULES = "/api/cajeros/rules"


def regla(db, *, cajero=7, autorizador=20, currency="ARS", limite="1000",
          reference=None, activa=True, autorizador_username="jefe20"):
    r = AuthorizationRule(cajero_user_id=cajero, authorizer_user_id=autorizador,
                          authorizer_username=autorizador_username, currency=currency,
                          amount_limit=limite, reference=reference, is_active=activa,
                          created_by=1)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def crear_tx(client, headers, **extra):
    payload = {"currency": "ARS", "amount": "500.00"}
    payload.update(extra)
    return client.post(BASE, json=payload, headers=headers)


# --- alta y evaluación de reglas -------------------------------------------------

def test_sin_reglas_la_transaccion_queda_procesada_y_no_notifica(client, h, notificaciones):
    r = crear_tx(client, h, amount="999999.00")
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["status"] == "PROCESADA"
    assert cuerpo["authorizer_user_id"] is None
    assert cuerpo["cajero_user_id"] == 7 and cuerpo["cajero_username"] == "cajero7"
    assert cuerpo["triggers"] == []
    assert notificaciones["notify_many"] == []


def test_monto_bajo_el_limite_no_dispara_la_regla(client, h, db, notificaciones):
    regla(db, limite="1000")
    assert crear_tx(client, h, amount="1000.00").json()["status"] == "PROCESADA"
    assert notificaciones["notify_many"] == []


def test_monto_sobre_el_limite_queda_pendiente_y_avisa_al_autorizador(client, h, db, notificaciones):
    r = regla(db, limite="1000")
    cuerpo = crear_tx(client, h, amount="1000.01", description="retiro grande").json()
    assert cuerpo["status"] == "PENDIENTE_AUTORIZACION"
    assert cuerpo["authorizer_user_id"] == 20 and cuerpo["authorizer_username"] == "jefe20"
    assert [t["rule_id"] for t in cuerpo["triggers"]] == [r.id]

    assert len(notificaciones["notify_many"]) == 1
    aviso = notificaciones["notify_many"][0][0]
    assert aviso["user_id"] == 20
    assert aviso["entity_type"] == "transaction" and aviso["entity_id"] == cuerpo["id"]
    assert aviso["redirect_path"] == f"/modules/cajeros/transactions/{cuerpo['id']}"
    assert "cajero7" in aviso["message"] and "ARS" in aviso["message"]


def test_las_reglas_acumulan_los_montos_previos_del_cajero(client, h, db):
    regla(db, limite="1000")
    assert crear_tx(client, h, amount="600").json()["status"] == "PROCESADA"
    # 600 previos + 600 nuevos > 1000: la segunda ya necesita autorización.
    assert crear_tx(client, h, amount="600").json()["status"] == "PENDIENTE_AUTORIZACION"


def test_las_eliminadas_no_suman_pero_las_rechazadas_si(client, h, db):
    regla(db, limite="1000")
    primera = crear_tx(client, h, amount="900").json()
    db.query(Transaction).filter_by(id=primera["id"]).one().status = "ELIMINADA"
    db.commit()
    assert crear_tx(client, h, amount="900").json()["status"] == "PROCESADA"

    # TODO(bug): rule_evaluator sólo excluye "ELIMINADA" (app/services/rule_evaluator.py:31),
    # así que una transacción RECHAZADA sigue consumiendo el cupo del cajero.
    db.query(Transaction).filter(Transaction.status == "PROCESADA").update({"status": "RECHAZADA"})
    db.commit()
    assert crear_tx(client, h, amount="200").json()["status"] == "PENDIENTE_AUTORIZACION"


def test_la_regla_de_otro_cajero_otra_moneda_o_inactiva_no_aplica(client, h, db):
    regla(db, cajero=99, limite="10")
    regla(db, currency="USD", limite="10")
    regla(db, limite="10", activa=False)
    assert crear_tx(client, h, amount="5000").json()["status"] == "PROCESADA"


def test_regla_con_referencia_solo_mira_esa_referencia(client, h, db):
    regla(db, limite="100", reference="CAJA-1")
    # Otra referencia: la regla ni siquiera se evalúa.
    assert crear_tx(client, h, amount="5000", reference="CAJA-2").json()["status"] == "PROCESADA"
    assert crear_tx(client, h, amount="5000").json()["status"] == "PROCESADA"
    # Misma referencia y sobre el límite: pendiente.
    assert crear_tx(client, h, amount="101", reference="CAJA-1").json()["status"] == "PENDIENTE_AUTORIZACION"


def test_varias_reglas_disparadas_dejan_un_trigger_por_regla_y_un_aviso_por_autorizador(
        client, h, db, notificaciones):
    regla(db, limite="100", autorizador=20)
    regla(db, limite="200", autorizador=21, autorizador_username="jefe21")
    regla(db, limite="300", autorizador=20)  # mismo autorizador que la primera

    cuerpo = crear_tx(client, h, amount="1000").json()
    assert len(cuerpo["triggers"]) == 3
    # El autorizador primario es el de la primera regla disparada.
    assert cuerpo["authorizer_user_id"] == 20
    avisos = notificaciones["notify_many"][0]
    assert sorted(a["user_id"] for a in avisos) == [20, 21]


def test_alta_sin_identidad_o_con_monto_invalido(client, h):
    assert crear_tx(client, {}).status_code == 422
    assert crear_tx(client, {"X-User-Id": "x"}).status_code == 401
    assert crear_tx(client, h, amount="no-es-plata").status_code == 422
    assert client.post(BASE, json={"currency": "ARS"}, headers=h).status_code == 422


# --- visibilidad del listado ------------------------------------------------------

def test_sin_read_all_solo_ve_las_propias_y_las_que_debe_autorizar(client, h, h_auth, db):
    regla(db, limite="100")
    crear_tx(client, h, amount="500")                       # de 7, pendiente para 20
    crear_tx(client, {"X-User-Id": "8"}, amount="10")        # de otro cajero, procesada

    mias = client.get(BASE, headers=h).json()
    assert [t["cajero_user_id"] for t in mias] == [7]

    del_autorizador = client.get(BASE, headers=h_auth).json()
    assert [t["cajero_user_id"] for t in del_autorizador] == [7]

    de_un_tercero = client.get(BASE, headers={"X-User-Id": "8"}).json()
    assert [t["cajero_user_id"] for t in de_un_tercero] == [8]


def test_read_all_y_admin_ven_todas(client, h, db):
    crear_tx(client, h, amount="10")
    crear_tx(client, {"X-User-Id": "8"}, amount="10")

    read_all = {"X-User-Id": "50", "X-User-Permissions": "cajeros:transactions:read,cajeros:transactions:read_all"}
    assert len(client.get(BASE, headers=read_all).json()) == 2

    admin = {"X-User-Id": "51", "X-User-Permissions": "cajeros:transactions:admin"}
    assert len(client.get(BASE, headers=admin).json()) == 2

    # Un permiso que no habilita el listado global: sólo lo propio.
    solo_read = {"X-User-Id": "52", "X-User-Permissions": "cajeros:transactions:read"}
    assert client.get(BASE, headers=solo_read).json() == []


def test_listado_filtra_por_estado_moneda_y_cajero(client, h, db):
    regla(db, limite="100", currency="USD")
    crear_tx(client, h, amount="10", currency="ARS")
    crear_tx(client, h, amount="500", currency="USD")       # pendiente
    crear_tx(client, {"X-User-Id": "8"}, amount="10")

    admin = {"X-User-Id": "50", "X-User-Permissions": "cajeros:transactions:admin"}
    assert len(client.get(f"{BASE}?currency=USD", headers=admin).json()) == 1
    assert len(client.get(f"{BASE}?cajero=8", headers=admin).json()) == 1
    assert len(client.get(f"{BASE}?status=PROCESADA", headers=admin).json()) == 2
    # El filtro de estado acepta varios separados por coma.
    combinados = client.get(f"{BASE}?status=PROCESADA,PENDIENTE_AUTORIZACION", headers=admin).json()
    assert len(combinados) == 3


def test_listado_pone_primero_las_pendientes(client, h, db):
    crear_tx(client, h, amount="10")
    regla(db, limite="1")
    crear_tx(client, h, amount="10")
    estados = [t["status"] for t in client.get(BASE, headers=h).json()]
    assert estados[0] == "PENDIENTE_AUTORIZACION"


def test_listado_ignora_las_fechas_recibidas(client, h, db):
    # TODO(bug): el router acepta date_from/date_to pero no se los pasa al servicio
    # (app/routers/transactions.py:44): el filtro por fecha se descarta en silencio.
    crear_tx(client, h, amount="10")
    r = client.get(f"{BASE}?date_from=2099-01-01&date_to=2099-12-31", headers=h)
    assert len(r.json()) == 1

    # El servicio sí sabe filtrar por fecha; sólo que nadie se lo pide.
    from datetime import datetime, timedelta
    from app.services.transaction_service import get_transactions
    ahora = datetime.utcnow()
    assert get_transactions(db, 7, date_from=ahora + timedelta(days=1)) == []
    assert get_transactions(db, 7, date_to=ahora - timedelta(days=1)) == []
    assert len(get_transactions(db, 7, date_from=ahora - timedelta(days=1),
                                date_to=ahora + timedelta(days=1))) == 1


# --- detalle ----------------------------------------------------------------------

def test_detalle_y_404(client, h):
    tx_id = crear_tx(client, h).json()["id"]
    assert client.get(f"{BASE}/{tx_id}", headers=h).json()["id"] == tx_id
    assert client.get(f"{BASE}/9999", headers=h).status_code == 404
    assert client.get(f"{BASE}/no-numerico", headers=h).status_code == 422


def test_el_detalle_no_chequea_de_quien_es_la_transaccion(client, h):
    # TODO(bug): GET /transactions/{id} no valida identidad ni permisos
    # (app/routers/transactions.py:48-53): cualquier usuario lee cualquier transacción,
    # salteando la restricción del listado (transactions:read vs read_all).
    tx_id = crear_tx(client, h).json()["id"]
    r = client.get(f"{BASE}/{tx_id}", headers={"X-User-Id": "999"})
    assert r.status_code == 200 and r.json()["cajero_user_id"] == 7


# --- transiciones de estado -------------------------------------------------------

def _pendiente(client, h, db, amount="500"):
    regla(db, limite="100")
    return crear_tx(client, h, amount=amount).json()["id"]


def test_autorizar_cambia_el_estado_y_avisa_al_cajero(client, h, h_auth, db, notificaciones):
    tx_id = _pendiente(client, h, db)
    cuerpo = client.put(f"{BASE}/{tx_id}/authorize", headers=h_auth).json()
    assert cuerpo["status"] == "AUTORIZADA"
    assert cuerpo["authorizer_user_id"] == 20 and cuerpo["authorizer_username"] == "jefe20"
    assert cuerpo["authorized_at"] is not None

    aviso = notificaciones["notify"][-1]
    assert aviso["user_id"] == 7 and aviso["title"] == "Transacción autorizada"
    assert aviso["entity_id"] == tx_id and aviso["module"] == "cajeros"


def test_autorizar_dos_veces_da_400(client, h, h_auth, db):
    tx_id = _pendiente(client, h, db)
    client.put(f"{BASE}/{tx_id}/authorize", headers=h_auth)
    r = client.put(f"{BASE}/{tx_id}/authorize", headers=h_auth)
    assert r.status_code == 400 and "PENDIENTE_AUTORIZACION" in r.json()["detail"]


def test_autorizar_una_procesada_da_400_y_una_inexistente_404(client, h, h_auth):
    tx_id = crear_tx(client, h).json()["id"]
    assert client.put(f"{BASE}/{tx_id}/authorize", headers=h_auth).status_code == 400
    assert client.put(f"{BASE}/9999/authorize", headers=h_auth).status_code == 404


def test_solo_el_autorizador_asignado_puede_autorizar(client, h, db, notificaciones):
    tx_id = _pendiente(client, h, db)
    r = client.put(f"{BASE}/{tx_id}/authorize", headers={"X-User-Id": "21"})
    assert r.status_code == 403
    assert notificaciones["notify"] == []
    assert client.get(f"{BASE}/{tx_id}", headers=h).json()["status"] == "PENDIENTE_AUTORIZACION"


def test_rechazar_guarda_el_motivo_y_avisa(client, h, h_auth, db, notificaciones):
    tx_id = _pendiente(client, h, db)
    r = client.put(f"{BASE}/{tx_id}/reject", json={"rejection_reason": "faltan comprobantes"},
                   headers=h_auth)
    cuerpo = r.json()
    assert cuerpo["status"] == "RECHAZADA"
    assert cuerpo["rejection_reason"] == "faltan comprobantes"
    assert cuerpo["authorizer_user_id"] == 20

    aviso = notificaciones["notify"][-1]
    assert aviso["user_id"] == 7 and aviso["title"] == "Transacción rechazada"
    assert "faltan comprobantes" in aviso["message"]


def test_rechazar_exige_motivo_y_respeta_estado_y_autorizador(client, h, h_auth, db):
    tx_id = _pendiente(client, h, db)
    assert client.put(f"{BASE}/{tx_id}/reject", json={}, headers=h_auth).status_code == 422
    assert client.put(f"{BASE}/{tx_id}/reject", json={"rejection_reason": "no"},
                      headers={"X-User-Id": "21"}).status_code == 403
    assert client.put(f"{BASE}/9999/reject", json={"rejection_reason": "no"},
                      headers=h_auth).status_code == 404

    client.put(f"{BASE}/{tx_id}/reject", json={"rejection_reason": "no"}, headers=h_auth)
    assert client.put(f"{BASE}/{tx_id}/reject", json={"rejection_reason": "otra vez"},
                      headers=h_auth).status_code == 400


def test_el_cajero_dueno_elimina_su_transaccion_pendiente(client, h, db):
    tx_id = _pendiente(client, h, db)
    r = client.delete(f"{BASE}/{tx_id}", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "ELIMINADA"


def test_un_tercero_no_puede_eliminar_pero_el_admin_si(client, h, db):
    tx_id = _pendiente(client, h, db)
    assert client.delete(f"{BASE}/{tx_id}", headers={"X-User-Id": "8"}).status_code == 403
    # Ni siquiera el autorizador asignado: hace falta transactions:admin.
    assert client.delete(f"{BASE}/{tx_id}", headers={"X-User-Id": "20"}).status_code == 403
    admin = {"X-User-Id": "8", "X-User-Permissions": "cajeros:transactions:admin"}
    assert client.delete(f"{BASE}/{tx_id}", headers=admin).json()["status"] == "ELIMINADA"


def test_no_se_elimina_una_transaccion_ya_procesada(client, h):
    tx_id = crear_tx(client, h).json()["id"]
    r = client.delete(f"{BASE}/{tx_id}", headers=h)
    assert r.status_code == 400
    assert client.delete(f"{BASE}/9999", headers=h).status_code == 404


def test_la_transaccion_pendiente_registra_sus_triggers_en_la_base(client, h, db):
    tx_id = _pendiente(client, h, db)
    triggers = db.query(TransactionRuleTrigger).filter_by(transaction_id=tx_id).all()
    assert len(triggers) == 1 and triggers[0].authorizer_user_id == 20


def test_la_regla_creada_por_api_tambien_dispara(client, h):
    client.post(RULES, json={"cajero_user_id": 7, "authorizer_user_id": 20,
                             "currency": "ARS", "amount_limit": "50"}, headers=h)
    assert crear_tx(client, h, amount="51").json()["status"] == "PENDIENTE_AUTORIZACION"
