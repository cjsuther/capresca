from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import liquidaciones, internal
from app import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        scheduler.start()
    except Exception as e:
        print(f"[startup] Warning: no se pudo iniciar el scheduler de ingesta: {e}")
    yield
    scheduler.stop()


app = FastAPI(title="Liquidaciones Module", version="1.0.0", lifespan=lifespan)

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
