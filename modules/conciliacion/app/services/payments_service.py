"""
Motor de pagos salientes: por cada agencia con saldo a favor (saldo = depositado +
premios − adeudado > 0, es decir neto < 0), genera una transferencia desde la cuenta
de Capresca hacia la cuenta de cobro de la agencia.

Salvaguardas:
  - auto_payments_enabled=false  -> no hace nada (kill-switch).
  - payments_dry_run=true        -> registra la intención (status DRY_RUN) SIN llamar
                                    al banco. Ideal para validar antes de mover fondos.
  - Idempotencia: un pago ENVIADO por registro de conciliación; nunca paga dos veces.
  - payments_via_tesoreria=true  -> no paga directo: arma un lote en Tesorería (aprobación del
                                    tesorero + envío por Interbanking) y el pago queda EN_TESORERIA.
"""
import hashlib
import logging
import re
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.reconciliation_record import ReconciliationRecord
from app.models.reconciliation_payment import ReconciliationPayment
from app.services import clientes_client, interbanking_client, tesoreria_client

logger = logging.getLogger("conciliacion.payments")


async def _agencias_de_pago() -> dict[int, dict]:
    """client_id -> {cbu de cobro (el marcado is_payment_account, o el primero), cuit}."""
    agencies = await clientes_client.get_agencies()
    out: dict[int, dict] = {}
    for ag in agencies:
        cbus = ag.get("cbus") or []
        elegido = next((c for c in cbus if c.get("is_payment_account")), None) or (cbus[0] if cbus else None)
        if elegido and elegido.get("cbu"):
            out[ag["client_id"]] = {"cbu": elegido["cbu"], "cuit": ag.get("tax_id") or ""}
    return out


def _upsert_payment(db: Session, record: ReconciliationRecord, **fields) -> ReconciliationPayment:
    pay = db.query(ReconciliationPayment).filter(
        ReconciliationPayment.reconciliation_record_id == record.id
    ).first()
    if pay is None:
        pay = ReconciliationPayment(reconciliation_record_id=record.id)
        db.add(pay)
    for k, v in fields.items():
        setattr(pay, k, v)
    return pay


async def run_payments(db: Session, rec_date: date) -> dict:
    if not settings.auto_payments_enabled:
        return {"enabled": False}

    agencias = await _agencias_de_pago()
    records = db.query(ReconciliationRecord).filter(
        ReconciliationRecord.reconciliation_date == rec_date
    ).all()

    enviados = simulados = sin_cbu = errores = 0
    a_tesoreria: list = []
    for r in records:
        neto = (r.importe_adeudado or Decimal("0")) - (r.importe_premios or Decimal("0")) - (r.importe_depositado or Decimal("0"))
        saldo = -neto  # positivo = hay que pagarle a la agencia
        if saldo <= 0:
            continue

        # Idempotencia: si ya hay un pago ENVIADO, no repetir
        existente = db.query(ReconciliationPayment).filter(
            ReconciliationPayment.reconciliation_record_id == r.id
        ).first()
        # EN_TESORERIA espera el resultado; OBSERVADO lo frenó Tesorería (excluido/rechazado/fallido) y no
        # se reenvía solo cada hora: si el tesorero lo reintenta allá y se acredita, igual queda pagado.
        if existente and existente.status in ("ENVIADO", "EN_TESORERIA", "OBSERVADO"):
            continue

        cbu = (agencias.get(r.client_id) or {}).get("cbu")
        if not cbu:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=None, status="SIN_CBU",
                            error_message="La agencia no tiene cuenta de cobro (CBU) definida")
            sin_cbu += 1
            continue

        if settings.payments_via_tesoreria:
            a_tesoreria.append((r, saldo, cbu, (agencias.get(r.client_id) or {}).get("cuit", "")))
            continue

        if settings.payments_dry_run:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=cbu, status="DRY_RUN",
                            ib_transfer_id=None, error_message=None)
            if r.status == "A_VERIFICAR":
                r.status = "A_PAGAR"
            simulados += 1
            continue

        try:
            resp = await interbanking_client.create_payment(cbu, float(saldo), settings.payment_concepto)
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=cbu, status="ENVIADO",
                            ib_transfer_id=resp.get("id"), error_message=None)
            r.status = "PAGADO"
            enviados += 1
        except Exception as e:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number,
                            amount=saldo, cbu_destino=cbu, status="ERROR",
                            error_message=str(e)[:500])
            errores += 1

    db.commit()
    resultado = {"enabled": True, "dry_run": settings.payments_dry_run,
                 "enviados": enviados, "simulados": simulados, "sin_cbu": sin_cbu, "errores": errores}
    if settings.payments_via_tesoreria:
        resultado = {**resultado, "dry_run": False, **_mandar_a_tesoreria(db, rec_date, a_tesoreria)}
        resultado["errores"] += resultado.pop("rechazados")
    logger.info("Pagos %s: %s", rec_date, resultado)
    return resultado


def _mandar_a_tesoreria(db: Session, rec_date: date, items: list) -> dict:
    """Un lote por corrida. La referencia sale de los registros y del estado de su pago anterior: repetir
    la misma corrida (p. ej. tras un corte) cae en el mismo lote; tras un rechazo se arma uno nuevo."""
    if not items:
        return {"en_tesoreria": 0, "lote": None, "rechazados": 0}
    previos = {p.reconciliation_record_id: p for p in db.query(ReconciliationPayment).filter(
        ReconciliationPayment.reconciliation_record_id.in_([r.id for r, *_ in items])).all()}
    firma = ",".join(sorted(f"{r.id}:{getattr(previos.get(r.id), 'tesoreria_lote', None) or '-'}:"
                            f"{getattr(previos.get(r.id), 'error_message', None) or '-'}" for r, *_ in items))
    referencia = f"agencias {rec_date.isoformat()} {hashlib.sha1(firma.encode()).hexdigest()[:12]}"
    pagos = [{"referencia_externa": f"rec-{r.id}", "beneficiario": (r.agency_legal_name or r.agency_number or "")[:160],
              "documento": "".join(ch for ch in cuit if ch.isdigit())[:20], "cbu": cbu, "monto": float(saldo),
              "concepto": f"{settings.payment_concepto} {r.agency_number} {rec_date.isoformat()}"[:120]}
             for r, saldo, cbu, cuit in items]
    try:
        resp = tesoreria_client.enviar_lote(referencia, f"Pagos a agencias del {rec_date.strftime('%d/%m/%Y')}", pagos)
    except tesoreria_client.TesoreriaNoDisponible as e:
        for r, saldo, cbu, _ in items:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number, amount=saldo,
                            cbu_destino=cbu, status="ERROR", error_message=str(e)[:500])
        db.commit()
        return {"en_tesoreria": 0, "lote": None, "rechazados": len(items)}
    por_ref = {f"rec-{r.id}": (r, saldo, cbu) for r, saldo, cbu, _ in items}
    en_teso = rechazados = 0
    for p in resp.get("pagos", []):
        if p["referencia_externa"] in por_ref:
            r, saldo, cbu = por_ref[p["referencia_externa"]]
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number, amount=saldo,
                            cbu_destino=cbu, status="EN_TESORERIA", tesoreria_lote=resp["codigo"], error_message=None)
            en_teso += 1
    for x in resp.get("rechazados", []):
        if x.get("referencia_externa") not in por_ref:
            continue
        r, saldo, cbu = por_ref[x["referencia_externa"]]
        ya = re.search(r"Ya está en el lote (\S+)", x.get("motivo") or "")
        if ya:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number, amount=saldo,
                            cbu_destino=cbu, status="EN_TESORERIA", tesoreria_lote=ya.group(1), error_message=None)
            en_teso += 1
        else:
            _upsert_payment(db, r, client_id=r.client_id, agency_number=r.agency_number, amount=saldo,
                            cbu_destino=cbu, status="ERROR", error_message=f"Tesorería: {x.get('motivo')}"[:500])
            rechazados += 1
    db.commit()
    return {"en_tesoreria": en_teso, "lote": resp.get("codigo"), "rechazados": rechazados}


def aplicar_resultado_tesoreria(db: Session, lote: str, pagos: list[dict]) -> dict:
    """Aviso de Tesorería. CONFIRMADO → ENVIADO (pagado) y el registro queda PAGADO. FALLIDO / EXCLUIDO /
    RECHAZADO → OBSERVADO con el motivo (no se reenvía solo). Un aviso de un lote que ya no
    es el vigente del pago no lo toca (salvo CONFIRMADO: si la plata salió, queda pagado)."""
    pagados = fallidos = ignorados = 0
    for p in pagos:
        m = re.fullmatch(r"rec-(\d+)", p.get("referencia_externa") or "")
        pay = m and db.query(ReconciliationPayment).filter(
            ReconciliationPayment.reconciliation_record_id == int(m.group(1))).first()
        if not pay:
            ignorados += 1; continue
        if p["estado"] == "CONFIRMADO":
            if pay.status == "ENVIADO":
                ignorados += 1; continue
            pay.status, pay.tesoreria_lote, pay.error_message = "ENVIADO", lote, None
            rec = db.get(ReconciliationRecord, pay.reconciliation_record_id)
            if rec is not None:
                rec.status = "PAGADO"
            pagados += 1
        elif p["estado"] in ("FALLIDO", "EXCLUIDO", "RECHAZADO") and pay.status == "EN_TESORERIA" \
                and pay.tesoreria_lote == lote:
            pay.status = "OBSERVADO"
            pay.error_message = f"Tesorería ({p['estado'].lower()}): {p.get('motivo') or 'sin detalle'}"[:500]
            fallidos += 1
        else:
            ignorados += 1
    db.commit()
    return {"pagados": pagados, "fallidos": fallidos, "ignorados": ignorados}

