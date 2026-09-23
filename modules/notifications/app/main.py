from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import public, internal
from app.services import auditoria_central as central

app = FastAPI(title="Notifications Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router, prefix="/api/notifications")
app.include_router(internal.router)

# Auditoría central: sólo lo que hace el usuario (marcar leído / borrar). El alta la genera el sistema.
central.instalar(app)


@app.get("/health")
def health():
    return {"status": "ok", "service": "notifications"}
