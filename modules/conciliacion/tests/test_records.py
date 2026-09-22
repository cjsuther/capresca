"""Registros: edición manual, historial, vínculos, ajustes y boleta PDF."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.models.reconciliation_adjustment import ReconciliationAdjustment
from app.models.reconciliation_ib_link import ReconciliationIbLink
from app.models.reconciliation_status_history import ReconciliationStatusHistory
from app.schemas.reconciliation import RecordResponse
from conftest import FECHA, crear_registro, num, transferencia


def vincular(db, record, *, tx_id=10, tipo="transfer", monto="300.00",
             cbu="0720099620000001234501", match_type="AUTO", usuario=0):
    link = ReconciliationIbLink(
        reconciliation_record_id=record.id, ib_transaction_type=tipo,
        ib_transaction_id=tx_id, ib_amount=Decimal(monto), ib_cbu=cbu,
        ib_concepto="PAGO QUINIELA", match_type=match_type, linked_by_user_id=usuario,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


# ─────────────────────────────────────────────────────────────────────────────
# Lectura
# ─────────────────────────────────────────────────────────────────────────────
def test_traer_un_registro(client, db):
    rec = crear_registro(db, adeudado="1000", premios="100", depositado="400")

    r = client.get(f"/api/conciliacion/records/{rec.id}").json()

    assert r["id"] == rec.id and r["agency_number"] == "A001"
    # Los endpoints con response_model devuelven los importes como Decimal → string JSON
    # (los que responden un dict crudo, como GET /api/conciliacion, devuelven float).
    assert num(r["importe_neto"]) == Decimal("500")
    assert num(r["importe_adeudado"]) == Decimal("1000")


def test_traer_un_registro_inexistente_da_404(client):
    r = client.get("/api/conciliacion/records/999999")
    assert r.status_code == 404 and r.json()["detail"] == "Registro no encontrado"


def test_el_schema_de_respuesta_calcula_el_neto_desde_el_modelo(db):
    rec = crear_registro(db, adeudado="1000", premios="100", depositado="400")

    salida = RecordResponse.model_validate(rec)

    assert salida.importe_neto == Decimal("500.00")


# ─────────────────────────────────────────────────────────────────────────────
# Edición manual + historial
# ─────────────────────────────────────────────────────────────────────────────
def test_editar_importes_y_estado_deja_rastro_en_el_historial(client, h, db):
    rec = crear_registro(db, adeudado="1000", premios="100")

    r = client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={
        "importe_adeudado": "1200.00", "importe_premios": "150.00",
        "status": "CONSOLIDADO_MANUAL", "notes": "Ajuste acordado con la agencia",
    }).json()

    assert num(r["importe_adeudado"]) == Decimal("1200")
    assert num(r["importe_premios"]) == Decimal("150")
    assert r["status"] == "CONSOLIDADO_MANUAL"
    assert r["modified_by_user_id"] == 7 and r["modified_by_username"] == "operador"
    assert r["modified_at"] is not None

    hist = client.get(f"/api/conciliacion/records/{rec.id}/history").json()
    assert len(hist) == 1
    h0 = hist[0]
    assert h0["previous_status"] == "A_VERIFICAR" and h0["new_status"] == "CONSOLIDADO_MANUAL"
    assert Decimal(str(h0["previous_importe_adeudado"])) == Decimal("1000")
    assert Decimal(str(h0["new_importe_adeudado"])) == Decimal("1200")
    assert h0["changed_by_user_id"] == 7 and h0["notes"] == "Ajuste acordado con la agencia"


def test_editar_sin_cambios_igual_registra_el_historial(client, h, db):
    rec = crear_registro(db, adeudado="1000")

    client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={})

    assert db.query(ReconciliationStatusHistory).count() == 1


def test_el_historial_de_un_registro_inexistente_da_404(client):
    assert client.get("/api/conciliacion/records/999999/history").status_code == 404


def test_editar_un_registro_inexistente_da_404(client, h):
    assert client.put("/api/conciliacion/records/999999", headers=h, json={}).status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Vínculos con transacciones de Interbanking
# ─────────────────────────────────────────────────────────────────────────────
def test_agregar_un_vinculo_manual_sin_quitar_ninguno(client, h, db, servicios):
    """Vincular un depósito a mano desde la pantalla de edición.

    Antes fallaba con UnboundLocalError (500) salvo que en el mismo PUT se quitara otro vínculo:
    el import del modelo estaba dentro del `for` de los links a quitar.
    """
    rec = crear_registro(db, adeudado="1000")
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "300.00")]

    r = client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={
        "ib_links_to_add": [{"ib_transaction_type": "transfer", "ib_transaction_id": 10}],
    })

    assert r.status_code == 200, r.text
    link = db.query(ReconciliationIbLink).one()
    assert link.match_type == "MANUAL" and link.ib_transaction_id == 10
    assert num(r.json()["importe_depositado"]) == Decimal("300")


def test_agregar_y_quitar_vinculos_en_la_misma_edicion(client, h, db, servicios):
    """El único camino por el que hoy funciona agregar un vínculo manual."""
    rec = crear_registro(db, adeudado="1000")
    viejo = vincular(db, rec, tx_id=5, monto="100.00")
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "300.00")]

    r = client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={
        "ib_links_to_add": [{"ib_transaction_type": "transfer", "ib_transaction_id": 10}],
        "ib_links_to_remove": [viejo.id],
    }).json()

    nuevo_link = db.query(ReconciliationIbLink).filter_by(ib_transaction_id=10).one()
    assert nuevo_link.match_type == "MANUAL" and nuevo_link.linked_by_user_id == 7
    assert nuevo_link.ib_cbu == "0720099620000001234501"
    assert Decimal(str(nuevo_link.ib_amount)) == Decimal("300")
    # El importe devuelto ya refleja el cambio: se quitó el de 100 y se sumó el de 300.
    assert num(r["importe_depositado"]) == Decimal("300")


def test_agregar_un_vinculo_que_no_existe_en_interbanking_se_ignora(client, h, db, servicios):
    rec = crear_registro(db)
    servicios.transacciones = []

    r = client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={
        "ib_links_to_add": [{"ib_transaction_type": "transfer", "ib_transaction_id": 99}],
    })

    assert r.status_code == 200
    assert db.query(ReconciliationIbLink).count() == 0


def test_volver_a_vincular_la_misma_transaccion_al_mismo_registro_no_duplica(
        client, h, db, servicios):
    rec = crear_registro(db)
    vincular(db, rec, tx_id=10, match_type="MANUAL")
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "300.00")]

    client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={
        "ib_links_to_add": [{"ib_transaction_type": "transfer", "ib_transaction_id": 10}],
    })

    assert db.query(ReconciliationIbLink).count() == 1


def test_vincular_una_transaccion_que_estaba_en_otro_registro_la_mueve(
        client, h, db, servicios):
    origen = crear_registro(db, client_id=1, agency_number="A001", adeudado="1000")
    destino = crear_registro(db, client_id=2, agency_number="A002", adeudado="1000")
    vincular(db, origen, tx_id=10, monto="300.00")
    from app.services.link_service import recalculate_depositado
    recalculate_depositado(db, origen)
    db.commit()
    servicios.transacciones = [transferencia(10, "0720099620000001234501", "300.00")]

    suelto = vincular(db, destino, tx_id=999, monto="0.00")     # para que corra el import

    client.put(f"/api/conciliacion/records/{destino.id}", headers=h, json={
        "ib_links_to_add": [{"ib_transaction_type": "transfer", "ib_transaction_id": 10}],
        "ib_links_to_remove": [suelto.id],
    })

    movido = db.query(ReconciliationIbLink).filter_by(
        ib_transaction_id=10, unlinked_at=None).one()
    assert movido.reconciliation_record_id == destino.id
    anterior = db.query(ReconciliationIbLink).filter(
        ReconciliationIbLink.id != movido.id,
        ReconciliationIbLink.ib_transaction_id == 10).one()
    assert anterior.unlinked_at is not None and anterior.unlinked_by_user_id == 7
    db.refresh(origen)
    assert Decimal(str(origen.importe_depositado)) == Decimal("0")


def test_quitar_un_vinculo_desde_la_edicion_baja_el_depositado(client, h, db):
    rec = crear_registro(db, adeudado="1000", depositado="300")
    link = vincular(db, rec, monto="300.00")

    r = client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={
        "ib_links_to_remove": [link.id],
    }).json()

    assert num(r["importe_depositado"]) == Decimal("0")
    db.refresh(link)
    assert link.unlinked_at is not None


def test_quitar_un_vinculo_inexistente_o_ya_quitado_no_rompe(client, h, db):
    rec = crear_registro(db)
    link = vincular(db, rec)
    client.delete(f"/api/conciliacion/links/{link.id}", headers=h)

    r = client.put(f"/api/conciliacion/records/{rec.id}", headers=h, json={
        "ib_links_to_remove": [link.id, 999999],
    })

    assert r.status_code == 200


def test_desvincular_por_endpoint_devuelve_el_registro_recalculado(client, h, db):
    rec = crear_registro(db, adeudado="1000", depositado="300")
    link = vincular(db, rec, monto="300.00")

    r = client.delete(f"/api/conciliacion/links/{link.id}", headers=h).json()

    assert r["record"]["importe_depositado"] == 0.0
    assert r["record"]["importe_neto"] == 1000.0
    assert r["record"]["links"] == []
    db.refresh(link)
    assert link.unlinked_by_user_id == 7


def test_desvincular_un_link_inexistente_da_404(client, h):
    r = client.delete("/api/conciliacion/links/999999", headers=h)
    assert r.status_code == 404 and r.json()["detail"] == "Link no encontrado"


def test_desvincular_dos_veces_da_400(client, h, db):
    rec = crear_registro(db)
    link = vincular(db, rec)
    client.delete(f"/api/conciliacion/links/{link.id}", headers=h)

    r = client.delete(f"/api/conciliacion/links/{link.id}", headers=h)

    assert r.status_code == 400 and r.json()["detail"] == "El link ya está desvinculado"


def test_desvincular_un_link_huerfano_devuelve_record_nulo(client, h, db):
    """Vínculo apuntando a un registro borrado: el endpoint responde sin registro."""
    rec = crear_registro(db)
    link = vincular(db, rec)
    db.query(ReconciliationIbLink).filter_by(id=link.id).update(
        {"reconciliation_record_id": 999999})
    db.commit()

    r = client.delete(f"/api/conciliacion/links/{link.id}", headers=h).json()

    assert r == {"record": None}


# ─────────────────────────────────────────────────────────────────────────────
# Ajustes manuales
# ─────────────────────────────────────────────────────────────────────────────
def test_un_ajuste_positivo_acredita_a_la_agencia_y_puede_consolidarla(client, h, db):
    rec = crear_registro(db, adeudado="1000", premios="0")

    r = client.post(f"/api/conciliacion/records/{rec.id}/adjustments", headers=h,
                    json={"amount": 1000, "reason": "Depósito en efectivo en caja"}).json()

    assert num(r["importe_depositado"]) == Decimal("1000")
    assert num(r["importe_neto"]) == Decimal("0")
    assert r["status"] == "CONSOLIDADO"
    ajuste = db.query(ReconciliationAdjustment).one()
    assert ajuste.created_by_user_id == 7 and ajuste.created_by_username == "operador"
    assert ajuste.reason == "Depósito en efectivo en caja"


def test_un_ajuste_negativo_baja_el_saldo(client, h, db):
    rec = crear_registro(db, adeudado="1000", depositado="1000")
    vincular(db, rec, monto="1000.00")

    r = client.post(f"/api/conciliacion/records/{rec.id}/adjustments", headers=h,
                    json={"amount": -250.50, "reason": "Cheque rechazado"}).json()

    assert num(r["importe_depositado"]) == Decimal("749.50")
    assert num(r["importe_neto"]) == Decimal("250.50")
    assert r["status"] == "A_VERIFICAR"


def test_los_ajustes_conviven_con_los_vinculos_y_se_acumulan(client, h, db):
    rec = crear_registro(db, adeudado="1000")
    vincular(db, rec, monto="400.00")

    client.post(f"/api/conciliacion/records/{rec.id}/adjustments", headers=h,
                json={"amount": 100, "reason": "uno"})
    r = client.post(f"/api/conciliacion/records/{rec.id}/adjustments", headers=h,
                    json={"amount": 200, "reason": "dos"}).json()

    assert num(r["importe_depositado"]) == Decimal("700")


def test_un_ajuste_sin_justificacion_es_rechazado(client, h, db):
    rec = crear_registro(db, adeudado="1000")

    r = client.post(f"/api/conciliacion/records/{rec.id}/adjustments", headers=h,
                    json={"amount": 100, "reason": "   "})

    assert r.status_code == 400
    assert r.json()["detail"] == "El ajuste requiere una justificación"
    assert db.query(ReconciliationAdjustment).count() == 0


def test_ajustar_un_registro_inexistente_da_404(client, h):
    r = client.post("/api/conciliacion/records/999999/adjustments", headers=h,
                    json={"amount": 1, "reason": "x"})
    assert r.status_code == 404


def test_el_listado_de_ajustes_viene_del_mas_nuevo_al_mas_viejo(client, h, db):
    rec = crear_registro(db, adeudado="1000")
    client.post(f"/api/conciliacion/records/{rec.id}/adjustments", headers=h,
                json={"amount": 10, "reason": "uno"})
    client.post(f"/api/conciliacion/records/{rec.id}/adjustments", headers=h,
                json={"amount": -20, "reason": "dos"})

    filas = client.get(f"/api/conciliacion/records/{rec.id}/adjustments").json()

    assert len(filas) == 2
    assert {f["reason"] for f in filas} == {"uno", "dos"}
    assert {f["amount"] for f in filas} == {10.0, -20.0}
    assert all(f["created_by_username"] == "operador" for f in filas)


def test_un_registro_sin_ajustes_devuelve_lista_vacia(client, db):
    rec = crear_registro(db)
    assert client.get(f"/api/conciliacion/records/{rec.id}/adjustments").json() == []


# ─────────────────────────────────────────────────────────────────────────────
# Boleta PDF
# ─────────────────────────────────────────────────────────────────────────────
def test_la_boleta_es_un_pdf_valido(client, db):
    rec = crear_registro(db, adeudado="150000.00", premios="15000.00", depositado="135000.00",
                         status="CONSOLIDADO")

    r = client.get(f"/api/conciliacion/records/{rec.id}/boleta")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == \
        f'attachment; filename="boleta_{FECHA.isoformat()}_A001.pdf"'
    assert r.content.startswith(b"%PDF-")
    assert r.content.rstrip().endswith(b"%%EOF")
    assert len(r.content) > 1000


def test_la_boleta_de_una_agencia_sin_numero_usa_el_client_id(client, db):
    rec = crear_registro(db, client_id=55, agency_number=None, tax_id=None)

    r = client.get(f"/api/conciliacion/records/{rec.id}/boleta")

    assert r.headers["content-disposition"].endswith('_55.pdf"')
    assert r.content.startswith(b"%PDF-")


def test_la_boleta_usa_el_encabezado_y_pie_configurados(client, db):
    rec = crear_registro(db, adeudado="1000")
    db.execute(text("CREATE TABLE receipt_template_config "
                    "(id INTEGER PRIMARY KEY, header_text TEXT, footer_text TEXT, is_active BOOLEAN)"))
    db.execute(text("INSERT INTO receipt_template_config VALUES "
                    "(1, 'CAPRESCA — Comprobante', 'Documento no válido como factura', 1)"))
    db.commit()

    try:
        r = client.get(f"/api/conciliacion/records/{rec.id}/boleta")
        assert r.status_code == 200 and r.content.startswith(b"%PDF-")
    finally:
        db.execute(text("DROP TABLE receipt_template_config"))
        db.commit()


def test_la_boleta_de_un_registro_inexistente_da_404(client):
    assert client.get("/api/conciliacion/records/999999/boleta").status_code == 404


def test_el_pdf_se_genera_sin_plantilla_directamente(db):
    from app.services import pdf_service
    rec = crear_registro(db, adeudado="1000", premios="10", depositado="990")

    pdf = pdf_service.generate_boleta(rec, None)

    assert pdf.startswith(b"%PDF-")


def test_el_pdf_acepta_una_plantilla_a_medias(db):
    """Encabezado sí, pie no: la rama del pie no debe romper."""
    from app.services import pdf_service
    rec = crear_registro(db)

    class Plantilla:
        header_text = "CAPRESCA"
        footer_text = None

    assert pdf_service.generate_boleta(rec, Plantilla()).startswith(b"%PDF-")


def test_las_fechas_de_los_registros_creados_son_las_pedidas(db):
    rec = crear_registro(db)
    assert rec.reconciliation_date == FECHA
    assert rec.reconciliation_date != date.today()
