from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.clients import router as clients_router
from app.routers.cbus import router as cbus_router
from app.routers.internal import router as internal_router
from app.services import auditoria_central as central
from app.routers.documents import router as documents_router
from app.routers.padron import router as padron_router

app = FastAPI(title="Clientes Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients_router, prefix="/api/clientes")
app.include_router(cbus_router, prefix="/api/clientes")
app.include_router(documents_router, prefix="/api/clientes")
app.include_router(padron_router, prefix="/api/clientes")
app.include_router(internal_router)

# Auditoría central: altas, cambios y bajas del padrón (clientes, CBUs, documentos).
central.instalar(app)


@app.on_event("startup")
def _al_arrancar():
    """Una importación que quedó PROCESANDO murió con el proceso anterior: se marca para que la
    pantalla lo diga en vez de mostrar un avance congelado para siempre."""
    from app.db.session import SessionLocal
    from app.services.padron_import import marcar_interrumpidas
    db = SessionLocal()
    try:
        marcar_interrumpidas(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "clientes"}
