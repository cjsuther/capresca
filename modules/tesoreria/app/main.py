from fastapi import FastAPI

from app.routers import internal, lotes

app = FastAPI(title="Tesorería Module", version="1.0.0",
              description="Lotes de pagos: aprobación según workflow y envío por Interbanking.")

app.include_router(lotes.router, prefix="/api/tesoreria")
app.include_router(internal.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "tesoreria"}
