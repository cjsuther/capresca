from fastapi import FastAPI

from app.routers import anexo, importacion, resoluciones
from app.services import auditoria_central as central

app = FastAPI(title="Despacho Module", version="1.0.0",
              description="Resoluciones y disposiciones, sus modelos, el anexo y los expedientes.")

app.include_router(resoluciones.router, prefix="/api/despacho")
app.include_router(anexo.router, prefix="/api/despacho")
app.include_router(importacion.router, prefix="/api/despacho")

# Auditoría central: qué actos administrativos crea, edita, firma o anula cada usuario.
central.instalar(app)


@app.on_event("startup")
def _al_arrancar():
    """Una importación que quedó PROCESANDO murió con el proceso anterior: se marca para que la
    pantalla lo diga en vez de mostrar un avance congelado."""
    from app.db.session import SessionLocal
    from app.services.importacion import marcar_interrumpidas
    db = SessionLocal()
    try:
        marcar_interrumpidas(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok", "service": "despacho"}
