from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import limits, relations, requests, operations

app = FastAPI(title="Cajeros Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/cajeros"
app.include_router(limits.router, prefix=PREFIX)
app.include_router(relations.router, prefix=PREFIX)
app.include_router(requests.router, prefix=PREFIX)
app.include_router(operations.router, prefix=PREFIX)


@app.get("/health")
def health():
    return {"status": "ok", "service": "cajeros"}
