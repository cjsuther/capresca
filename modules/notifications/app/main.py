from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import public, internal

app = FastAPI(title="Notifications Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(public.router, prefix="/api/notifications")
app.include_router(internal.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "notifications"}
