from fastapi import FastAPI

from app.routers import internal, lotes
from app.services import auditoria_central as central

app = FastAPI(title="Tesorería Module", version="1.0.0",
              description="Lotes de pagos: aprobación según workflow y envío por Interbanking.")

app.include_router(lotes.router, prefix="/api/tesoreria")
app.include_router(internal.router)

# Auditoría central: qué registros cambia cada usuario. La bitácora del lote ya se manda con nombre de
# negocio desde `services/lotes.evento`, así que sus filas no se duplican acá.
central.instalar(app, excluir={"lote_eventos"})


@app.get("/health")
def health():
    return {"status": "ok", "service": "tesoreria"}
