import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.middleware.auth import AuthMiddleware
from app.routes.proxy import router as proxy_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="API Gateway", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(AuthMiddleware)

app.include_router(proxy_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "proxy"}
