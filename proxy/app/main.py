import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.auth import AuthMiddleware
from app.routes.proxy import router as proxy_router
from app.services import auditoria

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="API Gateway", version="1.0.0")

# El frontend se sirve desde el mismo dominio (nginx) y en desarrollo pasa por el proxy de Vite: no hace
# falta CORS. Sólo se habilitan los orígenes que se declaren en CORS_ORIGINS (separados por coma).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)

app.include_router(proxy_router)


@app.on_event("startup")
async def _arrancar_auditoria() -> None:
    await auditoria.iniciar()


@app.on_event("shutdown")
async def _parar_auditoria() -> None:
    await auditoria.detener()


@app.get("/health")
def health():
    return {"status": "ok", "service": "proxy"}
