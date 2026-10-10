from fastapi import FastAPI

from app.routers import internal, lotes, ordenes
from app.services import auditoria_central as central, contabilidad_central

app = FastAPI(title="Tesorería Module", version="1.0.0",
              description="Lotes de pagos y órdenes de pago de créditos: aprobación según workflow y envío por Interbanking.")

app.include_router(lotes.router, prefix="/api/tesoreria")
app.include_router(ordenes.router, prefix="/api/tesoreria")
app.include_router(internal.router)

# Auditoría central: qué registros cambia cada usuario. La bitácora del lote ya se manda con nombre de
# negocio desde `services/lotes.evento`, así que sus filas no se duplican acá.
central.instalar(app, excluir={"lote_eventos"})


@app.on_event("startup")
def _outbox_contable():
    """Reenvía las transacciones para Contabilidad que quedaron pendientes antes de un reinicio."""
    contabilidad_central.iniciar()


@app.get("/health")
def health():
    return {"status": "ok", "service": "tesoreria"}
