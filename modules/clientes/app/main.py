from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.clients import router as clients_router
from app.routers.cbus import router as cbus_router
from app.routers.internal import router as internal_router

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
app.include_router(internal_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "clientes"}
