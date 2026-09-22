from fastapi import FastAPI

from app.routers import feriados, impuestos, indices, internal, workflow
from app.services import auditoria_central as central

app = FastAPI(title="Configuraciones Module", version="1.0.0",
              description="Configuración compartida de Portezuelo: impuestos, índices, feriados y workflow.")

for r in (impuestos.router, indices.router, feriados.router, workflow.router):
    app.include_router(r, prefix="/api/configuraciones")
app.include_router(internal.router)

# Auditoría central: cambios de impuestos, índices, feriados y reglas del workflow.
central.instalar(app)


@app.get("/health")
def health():
    return {"status": "ok", "service": "configuraciones"}
