from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, users, roles, groups, modules, permissions, internal
from app.services import auditoria_central as central

app = FastAPI(title="Security Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas públicas (via proxy)
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api/security")
app.include_router(roles.router, prefix="/api/security")
app.include_router(groups.router, prefix="/api/security")
app.include_router(modules.router, prefix="/api/security")
app.include_router(permissions.router, prefix="/api/security")

# Rutas internas (solo accesibles desde el proxy dentro de la red Docker)
app.include_router(internal.router)

# Auditoría central: altas, cambios y bajas de usuarios, roles, grupos y permisos. La lista negra de
# tokens es ruido de sesión (un registro por logout), no un cambio de información.
central.instalar(app, excluir={"token_blacklist"})


@app.get("/health")
def health():
    return {"status": "ok", "service": "security"}
