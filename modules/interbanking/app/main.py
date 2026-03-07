from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import config, cuentas, transferencias, pagos, auditoria

app = FastAPI(title="Interbanking Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(config.router,          prefix="/api/interbanking/config")
app.include_router(cuentas.router,         prefix="/api/interbanking/cuentas")
app.include_router(transferencias.router,  prefix="/api/interbanking/transferencias")
app.include_router(pagos.router,           prefix="/api/interbanking/pagos")
app.include_router(auditoria.router,       prefix="/api/interbanking/auditoria")


@app.get("/health")
def health():
    return {"status": "ok", "service": "interbanking"}
