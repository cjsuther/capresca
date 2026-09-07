from decimal import Decimal
from collections import defaultdict

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.batch import LiquidacionBatch
from app.models.procesada import LiquidacionProcesada


def send_to_conciliacion(db: Session, batch: LiquidacionBatch):
    """Send aggregated liquidation data to the conciliacion module."""
    procesadas = db.query(LiquidacionProcesada).filter(
        LiquidacionProcesada.batch_id == batch.id
    ).all()

    # Aggregate by agency
    agency_data = defaultdict(lambda: {
        "importe_adeudado": Decimal("0"),
        "importe_premios": Decimal("0"),
        "recaudacion_total": Decimal("0"),
        "comision_total": Decimal("0"),
    })

    for p in procesadas:
        agen = p.n_agen.strip()
        agency_data[agen]["importe_adeudado"] += (p.total or Decimal("0")) - (p.premios or Decimal("0"))
        agency_data[agen]["importe_premios"] += p.premios or Decimal("0")
        agency_data[agen]["recaudacion_total"] += p.recaudacion or Decimal("0")
        agency_data[agen]["comision_total"] += p.comision or Decimal("0")

    agencies = []
    for agen, data in agency_data.items():
        agencies.append({
            "agency_number": agen,
            "operation_date": batch.operation_date.isoformat() if batch.operation_date else None,
            "importe_adeudado": float(data["importe_adeudado"]),
            "importe_premios": float(data["importe_premios"]),
            "recaudacion_total": float(data["recaudacion_total"]),
            "comision_total": float(data["comision_total"]),
            "resumen_number": batch.resumen_number,
            "moneda": "$",
            "batch_id": batch.id,
            "batch_source": "liquidaciones",
        })

    payload = {
        "batch_id": batch.id,
        "operation_date": batch.operation_date.isoformat() if batch.operation_date else None,
        "created_by": batch.created_by,
        "agencies": agencies,
    }

    with httpx.Client() as client:
        response = client.post(
            f"{settings.conciliacion_service_url}/internal/conciliacion/liquidaciones",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
