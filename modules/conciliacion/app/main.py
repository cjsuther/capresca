from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import conciliacion, links, boleta, internal
from app.services import cbu_cache_service
from app.db.session import SessionLocal
from app import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Rebuild CBU cache on startup
    db = SessionLocal()
    try:
        await cbu_cache_service.rebuild_cache(db)
    except Exception as e:
        print(f"[startup] Warning: could not rebuild CBU cache: {e}")
    finally:
        db.close()
    # Cruce automático horario
    try:
        scheduler.start()
    except Exception as e:
        print(f"[startup] Warning: no se pudo iniciar el scheduler: {e}")
    yield
    scheduler.stop()


app = FastAPI(title="Conciliacion Module", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/conciliacion"
app.include_router(conciliacion.router, prefix=PREFIX)
app.include_router(links.router, prefix=PREFIX)
app.include_router(boleta.router, prefix=PREFIX)
app.include_router(internal.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "conciliacion"}
