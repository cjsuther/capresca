from fastapi import FastAPI

from app.routers import feriados, impuestos, indices, internal, workflow

app = FastAPI(title="Configuraciones Module", version="1.0.0",
              description="Configuración compartida de Portezuelo: impuestos, índices, feriados y workflow.")

for r in (impuestos.router, indices.router, feriados.router, workflow.router):
    app.include_router(r, prefix="/api/configuraciones")
app.include_router(internal.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "configuraciones"}
