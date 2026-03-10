from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from app.db.session import get_db
from app.services import reconciliation_service, pdf_service
from app.models.reconciliation_record import ReconciliationRecord

router = APIRouter(tags=["boleta"])


@router.get("/records/{record_id}/boleta")
def download_boleta(record_id: int, db: Session = Depends(get_db)):
    record = reconciliation_service.get_record(db, record_id)
    # Try to get template
    from app.models.cbu_agency_cache import CbuAgencyCache
    template = None
    try:
        from app.db.base import Base
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        if "receipt_template_config" in inspector.get_table_names():
            from app.db.session import SessionLocal
            from sqlalchemy import text
            row = db.execute(text("SELECT * FROM receipt_template_config WHERE is_active = true LIMIT 1")).fetchone()
            if row:
                class T:
                    pass
                template = T()
                template.header_text = row[1] if len(row) > 1 else None
                template.footer_text = row[2] if len(row) > 2 else None
    except Exception:
        pass
    pdf_bytes = pdf_service.generate_boleta(record, template)
    filename = f"boleta_{record.reconciliation_date}_{record.agency_number or record.client_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
