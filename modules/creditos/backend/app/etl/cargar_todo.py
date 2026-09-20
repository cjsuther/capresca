"""Orquestador de ETL: corre todas las cargas reales en orden y, en PostgreSQL,
resetea las secuencias de las tablas con id explícito.

Uso:
    DATABASE_URL=postgresql+psycopg://ccypp:ccypp@db:5432/ccypp \
    python3 -m app.etl.cargar_todo "/bases"
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from app.core.database import Base, engine, SessionLocal
from app.etl import (cargar_maestros, cargar_seguros, cargar_creditos,
                     cargar_ctacte, cargar_despacho, cargar_egresos, cargar_juegos,
                     cargar_usuarios, cargar_auditoria, cargar_jubilados,
                     cargar_tramites, cargar_solicitudes, cargar_contable,
                     cargar_polizas, cargar_hisliq, cargar_cheques,
                     cargar_egresos_ledger, cargar_ccseguros,
                     cargar_asientos_pd, cargar_contab_caja)


# Tablas cargadas con id explícito (hay que resetear su secuencia en Postgres).
SECUENCIAS = ["organismos", "lineas_credito", "creditos"]


def resetear_secuencias():
    if not engine.url.get_backend_name().startswith("postgres"):
        return
    with engine.begin() as conn:
        for tabla in SECUENCIAS:
            conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {tabla}), 1))"))
    print("  secuencias reseteadas (Postgres)")


def main(bases: str):
    Base.metadata.create_all(bind=engine)
    print(">> ETL maestros");    cargar_maestros.cargar(bases)
    print(">> ETL seguros");     cargar_seguros.cargar(bases)
    print(">> ETL ccseguros");   cargar_ccseguros.cargar(bases)
    print(">> ETL créditos");    cargar_creditos.cargar(bases)
    print(">> ETL cta.cte.");    cargar_ctacte.cargar(bases)
    print(">> ETL despacho");    cargar_despacho.cargar(bases)
    print(">> ETL egresos");     cargar_egresos.cargar(bases)
    print(">> ETL cheques");     cargar_cheques.cargar(bases)
    print(">> ETL egr.ledger");  cargar_egresos_ledger.cargar(bases)
    print(">> ETL contable");    cargar_contable.cargar(bases)
    print(">> ETL asientos-pd"); cargar_asientos_pd.cargar(bases)
    print(">> ETL crctacte");    cargar_contab_caja.cargar_crctacte(bases)
    print(">> ETL contgral");    cargar_contab_caja.cargar_contgral(bases)
    print(">> ETL cj_crsghis");   cargar_contab_caja.cargar_crsghis(bases)
    print(">> ETL cj_liqhis");    cargar_contab_caja.cargar_liqhis(bases)
    print(">> ETL cj_paghis");    cargar_contab_caja.cargar_paghis(bases)
    print(">> ETL juegos");      cargar_juegos.cargar(bases)
    print(">> ETL hist.liq.");   cargar_hisliq.cargar(bases)
    print(">> ETL usuarios");    cargar_usuarios.cargar(bases)
    print(">> ETL auditoría");   cargar_auditoria.cargar(bases)
    print(">> ETL jubilados");   cargar_jubilados.cargar(bases)
    resetear_secuencias()
    print("ETL COMPLETO OK")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/bases")
