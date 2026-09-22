"""Módulo Contabilidad: recibe transacciones de los demás módulos y genera los asientos.

Ningún módulo manda asientos: mandan lo que pasó y acá se decide cómo se registra, con la definición
de cada tipo de transacción. Sin definición, la transacción queda pendiente de configuración.
"""
from fastapi import FastAPI

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.routers import gestion, internal
from app.seed import sembrar
from app.services import auditoria_central as central

app = FastAPI(title="Contabilidad", version="1.0.0",
              description="Plan de cuentas, ejercicios, definiciones de asiento, libros y estados contables.")

app.include_router(gestion.router, prefix="/api")
app.include_router(internal.router)

# Auditoría central: quién cambió el plan de cuentas, las definiciones o registró asientos. Las
# transacciones que llegan de otros módulos ya quedan registradas como tales acá.
central.instalar(app, excluir={"transacciones"})


@app.on_event("startup")
def arranque() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        sembrar(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "contabilidad"}
