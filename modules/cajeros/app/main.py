from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import rules, transactions
from app.services import auditoria_central as central

app = FastAPI(title="Cajeros Module", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api/cajeros"
app.include_router(rules.router, prefix=PREFIX)
app.include_router(transactions.router, prefix=PREFIX)

# Auditoría central (H-221): reglas, límites, solicitudes y transacciones que toca cada usuario.
central.instalar(app)


@app.get("/health")
def health():
    return {"status": "ok", "service": "cajeros"}
