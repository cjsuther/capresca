"""Validaciones del lote: detalle vs resumen, consistencia interna y conteo de agencias."""
from decimal import Decimal

from app.models.validacion import LiquidacionValidacion
from app.services.validation import validate_batch
from factories import resumen


def _procesada(n_agen="000123", total="1000.00", premios="0.00"):
    return {"n_agen": n_agen, "total": Decimal(total), "premios": Decimal(premios)}


def _por_tipo(validaciones, tipo):
    return [v for v in validaciones if v.validation_type == tipo]


def test_lote_coherente_pasa_las_tres_validaciones(db):
    vs = validate_batch(db, 1, [_procesada()], [resumen(importe="1000.00")])
    assert len(vs) == 3
    assert all(v.passed for v in vs)
    assert {v.validation_type for v in vs} == {
        "DETAIL_VS_SUMMARY", "INTERNAL_CONSISTENCY", "AGENCY_COUNT"}
    assert db.query(LiquidacionValidacion).filter_by(batch_id=1).count() == 3


def test_el_resumen_se_compara_contra_total_menos_premios(db):
    # total 1200 - premios 200 = 1000, que es lo que declara el resumen.
    vs = validate_batch(db, 1, [_procesada(total="1200.00", premios="200.00")],
                        [resumen(importe="1000.00")])
    dvs = _por_tipo(vs, "DETAIL_VS_SUMMARY")[0]
    assert dvs.passed and dvs.expected_value == Decimal("1000.00")
    assert dvs.actual_value == Decimal("1000.00")


def test_diferencia_de_un_centavo_entra_en_la_tolerancia(db):
    vs = validate_batch(db, 1, [_procesada(total="1000.01")], [resumen(importe="1000.00")])
    assert all(v.passed for v in vs)


def test_diferencia_mayor_a_la_tolerancia_falla(db):
    vs = validate_batch(db, 1, [_procesada(total="1000.50")], [resumen(importe="1000.00")])
    dvs = _por_tipo(vs, "DETAIL_VS_SUMMARY")[0]
    assert not dvs.passed
    assert "esperado=1000.00" in dvs.detail_message and "diff=0.50" in dvs.detail_message


def test_agencia_en_el_resumen_pero_no_en_el_detalle(db):
    vs = validate_batch(db, 1, [_procesada(n_agen="000123")],
                        [resumen(n_agen="000999", importe="500.00")])
    dvs = _por_tipo(vs, "DETAIL_VS_SUMMARY")[0]
    assert not dvs.passed and dvs.actual_value is None
    assert "presente en resumen pero no en detalle" in dvs.detail_message
    conteo = _por_tipo(vs, "AGENCY_COUNT")[0]
    assert not conteo.passed and "000999" in conteo.detail_message


def test_consistencia_interna_suma_todas_las_agencias(db):
    vs = validate_batch(
        db, 1,
        [_procesada("000123", "600.00"), _procesada("000456", "400.00")],
        [resumen(n_agen="000123", importe="600.00"), resumen(n_agen="000456", importe="400.00")],
    )
    ci = _por_tipo(vs, "INTERNAL_CONSISTENCY")[0]
    assert ci.passed and ci.expected_value == Decimal("1000.00")
    assert ci.agency_number is None


def test_consistencia_interna_falla_si_los_grandes_totales_no_cuadran(db):
    vs = validate_batch(db, 1, [_procesada(total="900.00")], [resumen(importe="1000.00")])
    ci = _por_tipo(vs, "INTERNAL_CONSISTENCY")[0]
    assert not ci.passed and "total procesado=900.00" in ci.detail_message


def test_agencias_de_mas_en_el_detalle_no_son_error(db):
    """El detalle puede traer agencias que el resumen no lista; sólo se exige el reverso."""
    vs = validate_batch(db, 1, [_procesada("000123"), _procesada("000456", "0.00")],
                        [resumen(n_agen="000123", importe="1000.00")])
    conteo = _por_tipo(vs, "AGENCY_COUNT")[0]
    assert conteo.passed
    assert conteo.expected_value == Decimal("1") and conteo.actual_value == Decimal("2")


def test_lote_sin_registros_valida_en_verde(db):
    vs = validate_batch(db, 1, [], [])
    assert len(vs) == 2 and all(v.passed for v in vs)  # sin resumen no hay DETAIL_VS_SUMMARY
