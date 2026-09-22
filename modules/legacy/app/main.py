from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import legacy, internal
from app import scheduler
from app.services import auditoria_central as central


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(title="Legacy Integration Module", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/legacy"
app.include_router(legacy.router, prefix=PREFIX)
app.include_router(internal.router)

# Auditoría central: lo que se manda al sistema viejo (outbox) y su estado. El espejo de sus tablas y la
# bitácora de interacciones no se auditan: son copia y registro del legacy, no acciones de un usuario.
ESPEJOS = {f"mirror_{n}" for n in ("maestrodio", "organismos", "cajaliq", "cajapagos", "cajaforpag",
                                   "cajacreseg", "maeclientes", "solicitud", "maecuotas", "lineacred",
                                   "maeagencias", "maejuegos")}
central.instalar(app, excluir={"legacy_interaction_log", "legacy_sync_state"} | ESPEJOS)


@app.get("/health")
def health():
    return {"status": "ok", "service": "legacy"}
