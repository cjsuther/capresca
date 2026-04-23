import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import conversations, webhook, menu_config, whatsapp_config, stats, internal

app = FastAPI(title="Comunicacion Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/comunicacion"
app.include_router(conversations.router, prefix=PREFIX)
app.include_router(menu_config.router, prefix=PREFIX)
app.include_router(whatsapp_config.router, prefix=PREFIX)
app.include_router(stats.router, prefix=PREFIX)
app.include_router(webhook.router)
app.include_router(internal.router)


@app.on_event("startup")
def startup():
    media_path = os.environ.get("MEDIA_STORAGE_PATH", "/data/comunicacion/media")
    os.makedirs(os.path.join(media_path, "inbound"), exist_ok=True)
    os.makedirs(os.path.join(media_path, "outbound"), exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok", "service": "comunicacion"}
