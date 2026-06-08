import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import config, cuentas, transferencias, auditoria
from app.routers import internal as internal_router

logger = logging.getLogger("interbanking")

app = FastAPI(title="Interbanking Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    body = None
    try:
        body = await request.json()
    except Exception:
        pass
    logger.warning(
        "Validation 422 on %s %s\n  errors=%s\n  body=%s",
        request.method, request.url.path, exc.errors(), body,
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

app.include_router(config.router,          prefix="/api/interbanking/config")
app.include_router(cuentas.router,         prefix="/api/interbanking/cuentas")
app.include_router(transferencias.router,  prefix="/api/interbanking/transferencias")
app.include_router(auditoria.router,       prefix="/api/interbanking/auditoria")
app.include_router(internal_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "interbanking"}
