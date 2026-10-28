from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import auth, documentos, metricas, trabajos, usuarios
from app.auth import admin_user, current_user
from app.core.config import settings

app = FastAPI(title="Procesamiento de documentos", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Todo lo que no es iniciar sesión pide una sesión válida (usuario de la tabla usuarios)
app.include_router(auth.router)
app.include_router(trabajos.router, dependencies=[Depends(current_user)])
app.include_router(documentos.router, dependencies=[Depends(current_user)])
app.include_router(metricas.router, dependencies=[Depends(current_user)])
# Perfiles: solo administradores
app.include_router(usuarios.router, dependencies=[Depends(admin_user)])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Frontend compilado (despliegue en un solo servicio). Se monta al final: las rutas de la API
# tienen prioridad y todo lo demás lo sirve el frontend.
if settings.FRONTEND_DIST and settings.FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIST, html=True), name="frontend")
