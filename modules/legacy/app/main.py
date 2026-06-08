from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import legacy, internal


app = FastAPI(title="Legacy Integration Module", version="1.0.0")

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


@app.get("/health")
def health():
    return {"status": "ok", "service": "legacy"}
