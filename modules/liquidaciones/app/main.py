from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import liquidaciones, internal


app = FastAPI(title="Liquidaciones Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/liquidaciones"
app.include_router(liquidaciones.router, prefix=PREFIX)
app.include_router(internal.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "liquidaciones"}
