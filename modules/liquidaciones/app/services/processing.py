from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.batch import LiquidacionBatch
from app.models.detalle_raw import LiquidacionDetalleRaw
from app.models.resumen_raw import LiquidacionResumenRaw
from app.models.procesada import LiquidacionProcesada
from app.models.archivo import LiquidacionArchivo
from app.services.zip_service import extract_zip, read_zip_from_path
from app.services.dbf_parser import parse_dbf, parse_importe
from app.services.validation import validate_batch
from app.services.conciliacion_client import send_to_conciliacion
from app.services.clientes_client import get_registered_agency_numbers


def process_batch(db: Session, zip_bytes: bytes, zip_filename: str, user_id: int) -> LiquidacionBatch:
    """Main processing pipeline."""
    batch = LiquidacionBatch(
        zip_filename=zip_filename,
        status="PROCESANDO",
        created_by=user_id,
    )
    db.add(batch)
    db.flush()

    try:
        # 1. Extract ZIP
        extracted = extract_zip(zip_bytes)

        # 2. Store files
        _store_files(db, batch.id, zip_bytes, zip_filename, extracted)

        # 3. Parse and store raw detail records
        detail_records = parse_dbf(extracted["dbf_detail"])
        raw_details = _store_detail_raw(db, batch.id, detail_records)

        # 4. Parse and store raw summary records
        summary_records = parse_dbf(extracted["dbf_summary"])
        raw_summaries = _store_summary_raw(db, batch.id, summary_records)

        # 5. Validate agencies exist in clientes module
        file_agencies = set(r.get("N_AGEN", "").strip() for r in detail_records if r.get("N_AGEN", "").strip())
        try:
            registered = get_registered_agency_numbers()
        except Exception as e:
            raise ValueError(f"No se pudo validar agencias contra módulo Clientes: {e}")
        unknown = file_agencies - registered
        if unknown:
            raise ValueError(
                f"Agencia(s) no registrada(s) en el módulo Clientes: {', '.join(sorted(unknown))}. "
                f"Registre las agencias antes de procesar la liquidación."
            )

        # 6. Aggregate details
        processed = aggregate_details(detail_records)
        _store_processed(db, batch.id, processed)

        # 7. Update batch metadata
        operation_date = _extract_operation_date(detail_records)
        resumen_number = _extract_resumen_number(detail_records)
        agencies = set(r["n_agen"] for r in processed)

        batch.operation_date = operation_date
        batch.resumen_number = resumen_number
        batch.total_detail_records = len(detail_records)
        batch.total_summary_records = len(summary_records)
        batch.total_agencies = len(agencies)
        batch.processed_at = datetime.now()

        # 8. Validate
        validations = validate_batch(db, batch.id, processed, summary_records)
        all_passed = all(v.passed for v in validations)

        if all_passed:
            batch.status = "VALIDADO"
            db.flush()
            # 9. Auto-send to conciliacion
            try:
                send_to_conciliacion(db, batch)
                batch.status = "ENVIADO_CONCILIACION"
                batch.sent_to_conciliacion_at = datetime.now()
            except Exception as e:
                batch.error_message = f"Validación OK pero falló envío a conciliación: {str(e)}"
                batch.status = "VALIDADO"
        else:
            failed = [v for v in validations if not v.passed]
            batch.status = "ERROR"
            batch.error_message = f"{len(failed)} validación(es) fallida(s)"

        db.commit()
        return batch

    except Exception as e:
        db.rollback()
        # Re-create batch after rollback since the original was discarded
        batch = LiquidacionBatch(
            zip_filename=zip_filename,
            status="ERROR",
            error_message=str(e),
            created_by=user_id,
            processed_at=datetime.now(),
        )
        db.add(batch)
        db.commit()
        return batch


def process_from_path(db: Session, file_path: str, user_id: int) -> LiquidacionBatch:
    """Process a ZIP from a filesystem path."""
    zip_bytes = read_zip_from_path(file_path)
    filename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    return process_batch(db, zip_bytes, filename, user_id)


def process_from_upload(db: Session, zip_bytes: bytes, filename: str, user_id: int) -> LiquidacionBatch:
    """Process a ZIP from an HTTP upload."""
    return process_batch(db, zip_bytes, filename, user_id)


def aggregate_details(raw_records: list[dict]) -> list[dict]:
    """Group raw M.dbf records by (N_AGEN, C_JUEGO, N_SORTEO) and classify codes."""
    groups = defaultdict(lambda: {
        "recaudacion": Decimal("0"),
        "premios": Decimal("0"),
        "comision": Decimal("0"),
        "fdo_gtia": Decimal("0"),
        "ing_brutos": Decimal("0"),
        "debitos": Decimal("0"),
        "creditos": Decimal("0"),
        "total": Decimal("0"),
        "modalidad": 0,
        "d_juego": "",
        "moneda": "",
        "no_recibo": 0,
        "d_operac": "",
    })

    for rec in raw_records:
        n_agen = rec.get("N_AGEN", "").strip()
        c_juego = rec.get("C_JUEGO", "").strip()
        n_sorteo = rec.get("N_SORTEO", "").strip()
        key = (n_agen, c_juego, n_sorteo)

        g = groups[key]
        importe = parse_importe(rec.get("IMPORTE", "0"))
        codigo = int(rec.get("C_CODIGO", "0").strip() or "0")
        juego = int(c_juego or "0")

        # Keep metadata from first record in group
        if not g["d_juego"]:
            g["d_juego"] = rec.get("D_JUEGO", "").strip()
        if not g["moneda"]:
            g["moneda"] = rec.get("C_MONEDA", "").strip()
        if not g["d_operac"]:
            g["d_operac"] = rec.get("D_OPERAC", "").strip()
        resumen = rec.get("C_RESUMEN", "").strip()
        if resumen:
            try:
                g["no_recibo"] = int(resumen)
            except ValueError:
                pass

        # Classification logic from FoxPro
        if codigo == 1:
            g["recaudacion"] += importe
            g["total"] += importe
        elif codigo == 581:
            g["recaudacion"] -= importe
            g["total"] -= importe
        elif codigo == 3:
            g["ing_brutos"] += importe
            g["total"] += importe
        elif codigo == 583:
            g["ing_brutos"] -= importe
            g["total"] -= importe
        elif codigo == 551:
            g["premios"] += importe
        elif codigo == 570:
            g["premios"] += importe
        elif codigo == 550:
            g["comision"] += importe
            g["total"] -= importe
        elif codigo == 30:
            g["comision"] -= importe
            g["total"] += importe
        elif codigo == 23:
            g["fdo_gtia"] += importe
            g["total"] += importe
        elif codigo == 24:
            g["debitos"] += importe
            g["total"] += importe
        elif juego == 50 and codigo == 43:
            g["recaudacion"] += importe
            g["total"] += importe
            g["modalidad"] = 43
            g["d_juego"] = rec.get("D_CODIGO", "").strip()
        else:
            if codigo < 500:
                g["debitos"] += importe
                g["total"] += importe
            else:
                g["creditos"] += importe
                g["total"] -= importe

    result = []
    for (n_agen, c_juego, n_sorteo), g in groups.items():
        result.append({
            "n_agen": n_agen,
            "c_juego": int(c_juego or "0"),
            "d_juego": g["d_juego"],
            "n_sorteo": int(n_sorteo or "0"),
            "modalidad": g["modalidad"],
            "moneda": g["moneda"] or "$",
            "recaudacion": g["recaudacion"],
            "premios": g["premios"],
            "comision": g["comision"],
            "fdo_gtia": g["fdo_gtia"],
            "ing_brutos": g["ing_brutos"],
            "debitos": g["debitos"],
            "creditos": g["creditos"],
            "total": g["total"],
            "no_recibo": g["no_recibo"],
            "d_operac": g["d_operac"],
        })

    return result


def _store_files(db: Session, batch_id: int, zip_bytes: bytes, zip_filename: str, extracted: dict):
    """Store ZIP and extracted files in the database."""
    files = [
        LiquidacionArchivo(
            batch_id=batch_id, file_type="ZIP",
            original_filename=zip_filename,
            file_data=zip_bytes, file_size=len(zip_bytes),
        ),
    ]
    if extracted.get("dbf_detail"):
        files.append(LiquidacionArchivo(
            batch_id=batch_id, file_type="DBF_DETALLE",
            original_filename=extracted["filenames"].get("dbf_detail", "detalle.dbf"),
            file_data=extracted["dbf_detail"], file_size=len(extracted["dbf_detail"]),
        ))
    if extracted.get("dbf_summary"):
        files.append(LiquidacionArchivo(
            batch_id=batch_id, file_type="DBF_RESUMEN",
            original_filename=extracted["filenames"].get("dbf_summary", "resumen.dbf"),
            file_data=extracted["dbf_summary"], file_size=len(extracted["dbf_summary"]),
        ))
    if extracted.get("pdf_movimientos"):
        files.append(LiquidacionArchivo(
            batch_id=batch_id, file_type="PDF_MOVIMIENTOS",
            original_filename=extracted["filenames"].get("pdf_movimientos", "movimientos.pdf"),
            file_data=extracted["pdf_movimientos"], file_size=len(extracted["pdf_movimientos"]),
        ))
    if extracted.get("pdf_resumenes"):
        files.append(LiquidacionArchivo(
            batch_id=batch_id, file_type="PDF_RESUMENES",
            original_filename=extracted["filenames"].get("pdf_resumenes", "resumenes.pdf"),
            file_data=extracted["pdf_resumenes"], file_size=len(extracted["pdf_resumenes"]),
        ))
    db.add_all(files)
    db.flush()


def _store_detail_raw(db: Session, batch_id: int, records: list[dict]) -> list[LiquidacionDetalleRaw]:
    """Bulk insert raw detail records."""
    rows = []
    for rec in records:
        rows.append(LiquidacionDetalleRaw(
            batch_id=batch_id,
            n_agen=rec.get("N_AGEN", "").strip(),
            c_juego=rec.get("C_JUEGO", "").strip(),
            d_juego=rec.get("D_JUEGO", "").strip(),
            n_sorteo=rec.get("N_SORTEO", "").strip(),
            c_codigo=rec.get("C_CODIGO", "").strip(),
            d_codigo=rec.get("D_CODIGO", "").strip(),
            d_operac=rec.get("D_OPERAC", "").strip(),
            importe=parse_importe(rec.get("IMPORTE", "0")),
            c_moneda=rec.get("C_MONEDA", "").strip(),
            c_resumen=rec.get("C_RESUMEN", "").strip(),
        ))
    db.add_all(rows)
    db.flush()
    return rows


def _store_summary_raw(db: Session, batch_id: int, records: list[dict]) -> list[LiquidacionResumenRaw]:
    """Bulk insert raw summary records."""
    rows = []
    for rec in records:
        rows.append(LiquidacionResumenRaw(
            batch_id=batch_id,
            c_juego=rec.get("C_JUEGO", "").strip(),
            n_agen=rec.get("N_AGEN", "").strip(),
            d_operac=rec.get("D_OPERAC", "").strip(),
            importe=parse_importe(rec.get("IMPORTE", "0")),
            c_moneda=rec.get("C_MONEDA", "").strip(),
            c_resumen=rec.get("C_RESUMEN", "").strip(),
            f_movin=rec.get("F_MOVIN", "").strip() if rec.get("F_MOVIN") else None,
        ))
    db.add_all(rows)
    db.flush()
    return rows


def _store_processed(db: Session, batch_id: int, processed: list[dict]):
    """Bulk insert aggregated/processed records."""
    rows = []
    for p in processed:
        operation_date = _parse_date(p.get("d_operac", ""))
        rows.append(LiquidacionProcesada(
            batch_id=batch_id,
            n_agen=p["n_agen"],
            c_juego=p["c_juego"],
            d_juego=p["d_juego"],
            n_sorteo=p["n_sorteo"],
            modalidad=p["modalidad"],
            moneda=p["moneda"],
            recaudacion=p["recaudacion"],
            premios=p["premios"],
            comision=p["comision"],
            fdo_gtia=p["fdo_gtia"],
            ing_brutos=p["ing_brutos"],
            debitos=p["debitos"],
            creditos=p["creditos"],
            total=p["total"],
            no_recibo=p["no_recibo"],
            operation_date=operation_date,
        ))
    db.add_all(rows)
    db.flush()


def _extract_operation_date(records: list[dict]) -> date | None:
    """Extract the operation date from the first record."""
    if not records:
        return None
    d_operac = records[0].get("D_OPERAC", "").strip()
    return _parse_date(d_operac)


def _extract_resumen_number(records: list[dict]) -> str | None:
    """Extract the resumen number from the first record."""
    if not records:
        return None
    return records[0].get("C_RESUMEN", "").strip() or None


def _parse_date(date_str: str) -> date | None:
    """Parse date string in DD/MM/YYYY format."""
    if not date_str:
        return None
    try:
        parts = date_str.split("/")
        if len(parts) == 3:
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        pass
    return None
