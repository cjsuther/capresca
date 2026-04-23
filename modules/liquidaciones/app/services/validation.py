from decimal import Decimal
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.validacion import LiquidacionValidacion
from app.services.dbf_parser import parse_importe

TOLERANCE = Decimal("0.01")


def validate_batch(
    db: Session,
    batch_id: int,
    processed: list[dict],
    summary_records: list[dict],
) -> list[LiquidacionValidacion]:
    """Run all validations and store results."""
    validations = []

    validations.extend(_validate_detail_vs_summary(db, batch_id, processed, summary_records))
    validations.extend(_validate_internal_consistency(db, batch_id, processed, summary_records))
    validations.extend(_validate_agency_count(db, batch_id, processed, summary_records))

    db.add_all(validations)
    db.flush()
    return validations


def _validate_detail_vs_summary(
    db: Session,
    batch_id: int,
    processed: list[dict],
    summary_records: list[dict],
) -> list[LiquidacionValidacion]:
    """For each agency in R.dbf, verify SUM(total) - SUM(premios) matches R.importe."""
    validations = []

    # Build per-agency totals from processed data
    agency_totals = defaultdict(lambda: {"total": Decimal("0"), "premios": Decimal("0")})
    for p in processed:
        agen = p["n_agen"].strip()
        agency_totals[agen]["total"] += p["total"]
        agency_totals[agen]["premios"] += p["premios"]

    # Compare against summary
    for rec in summary_records:
        agen = rec.get("N_AGEN", "").strip()
        expected = parse_importe(rec.get("IMPORTE", "0"))
        totals = agency_totals.get(agen)

        if totals is None:
            validations.append(LiquidacionValidacion(
                batch_id=batch_id,
                validation_type="DETAIL_VS_SUMMARY",
                agency_number=agen,
                expected_value=expected,
                actual_value=None,
                passed=False,
                detail_message=f"Agencia {agen} presente en resumen pero no en detalle",
            ))
            continue

        actual = totals["total"] - totals["premios"]
        diff = abs(expected - actual)
        passed = diff <= TOLERANCE

        validations.append(LiquidacionValidacion(
            batch_id=batch_id,
            validation_type="DETAIL_VS_SUMMARY",
            agency_number=agen,
            expected_value=expected,
            actual_value=actual,
            passed=passed,
            detail_message=(
                f"Agencia {agen}: OK (diff={diff})"
                if passed
                else f"Agencia {agen}: esperado={expected}, actual={actual}, diff={diff}"
            ),
        ))

    return validations


def _validate_internal_consistency(
    db: Session,
    batch_id: int,
    processed: list[dict],
    summary_records: list[dict],
) -> list[LiquidacionValidacion]:
    """Sum of all R.dbf amounts should equal grand total of all processed agencies."""
    summary_total = sum(parse_importe(r.get("IMPORTE", "0")) for r in summary_records)
    processed_total = sum(p["total"] - p["premios"] for p in processed)

    diff = abs(summary_total - processed_total)
    passed = diff <= TOLERANCE

    return [LiquidacionValidacion(
        batch_id=batch_id,
        validation_type="INTERNAL_CONSISTENCY",
        expected_value=summary_total,
        actual_value=processed_total,
        passed=passed,
        detail_message=(
            f"Consistencia interna OK (diff={diff})"
            if passed
            else f"Total resumen={summary_total}, total procesado={processed_total}, diff={diff}"
        ),
    )]


def _validate_agency_count(
    db: Session,
    batch_id: int,
    processed: list[dict],
    summary_records: list[dict],
) -> list[LiquidacionValidacion]:
    """Number of distinct agencies in detail should be >= agencies in summary."""
    detail_agencies = set(p["n_agen"].strip() for p in processed)
    summary_agencies = set(r.get("N_AGEN", "").strip() for r in summary_records)

    missing = summary_agencies - detail_agencies
    passed = len(missing) == 0

    return [LiquidacionValidacion(
        batch_id=batch_id,
        validation_type="AGENCY_COUNT",
        expected_value=Decimal(str(len(summary_agencies))),
        actual_value=Decimal(str(len(detail_agencies))),
        passed=passed,
        detail_message=(
            f"Conteo de agencias OK: {len(detail_agencies)} en detalle, {len(summary_agencies)} en resumen"
            if passed
            else f"Agencias faltantes en detalle: {', '.join(sorted(missing))}"
        ),
    )]
