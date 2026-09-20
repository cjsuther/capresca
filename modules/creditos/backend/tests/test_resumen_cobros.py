"""Resumen de cobros de créditos por período (frm330150000rptcobcre): agrega las cuotas pagadas
por mes; la mora sale como residual (total pagado − conceptos). Ver informe de cobros de créditos."""
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./_resumen_cobros.db"
os.environ["ENVIRONMENT"] = "development"

from datetime import date
from decimal import Decimal as D

import pytest


@pytest.fixture()
def db():
    from app.core.database import SessionLocal
    from app.main import app
    from fastapi.testclient import TestClient
    with TestClient(app):
        s = SessionLocal()
        try:
            yield s
        finally:
            s.rollback(); s.close()


def _cuota(cred, n, fecha_pago, cap, intr, iva, total):
    from app import models
    return models.Cuota(credito_id=cred, numero=n, fecha_vencimiento=date(2026, 3, 10),
                        saldo_capital=0, amortizacion=cap, interes=intr, iva_interes=iva,
                        seguro=0, iva_seguro=0, gastos_adm=0, iva_gastos_adm=0,
                        total=total, total_pagado=total, estado="P", fecha_pago=fecha_pago)


def test_resumen_agrega_por_periodo_y_mora_residual(db):
    from app import models
    from app.services.consultas import resumen_cobros_creditos
    db.query(models.Cuota).filter(models.Cuota.credito_id.in_([90001, 90002])).delete()
    db.commit()
    # 2 cuotas pagadas en 2026-03 de 2 créditos distintos; una con mora (total > conceptos)
    db.add(_cuota(90001, 1, date(2026, 3, 5), cap=D("1000"), intr=D("200"), iva=D("42"), total=D("1242")))
    db.add(_cuota(90002, 1, date(2026, 3, 20), cap=D("1000"), intr=D("200"), iva=D("42"), total=D("1300")))  # +58 mora
    # una pagada en otro mes (no debe mezclarse)
    db.add(_cuota(90001, 2, date(2026, 4, 5), cap=D("500"), intr=D("100"), iva=D("21"), total=D("621")))
    db.commit()

    r = resumen_cobros_creditos(db, desde=date(2026, 3, 1), hasta=date(2026, 3, 31))
    assert len(r["items"]) == 1
    mar = r["items"][0]
    assert mar["periodo"] == "2026-03"
    assert mar["cuotas"] == 2 and mar["creditos"] == 2
    assert mar["capital"] == D("2000") and mar["interes"] == D("400") and mar["iva"] == D("84")
    assert mar["mora"] == D("58")             # residual: (1242+1300) − (2000+400+84) = 58
    assert mar["total"] == D("2542")
    db.query(models.Cuota).filter(models.Cuota.credito_id.in_([90001, 90002])).delete()
    db.commit()
