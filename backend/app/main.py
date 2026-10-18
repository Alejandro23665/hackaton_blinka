import base64
import binascii
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.api import decisions, documents, exchange_rates, invoices, policies, vendors
from app.core.config import settings

app = FastAPI(title="Rekreuz API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas abiertas aunque haya contraseña: la plataforma de despliegue comprueba /health
PUBLIC_PATHS = {"/health"}


def _authorized(header: str | None) -> bool:
    if not header or not header.lower().startswith("basic "):
        return False
    try:
        user, _, password = base64.b64decode(header[6:], validate=True).decode("utf-8").partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False
    # compare_digest: no revela por el tiempo de respuesta cuántos caracteres coinciden
    return secrets.compare_digest(user, settings.ACCESS_USER) and secrets.compare_digest(
        password, settings.ACCESS_PASSWORD or ""
    )


@app.middleware("http")
async def require_password(request: Request, call_next):
    """Si ACCESS_PASSWORD está definida, la app (página y API) pide usuario y contraseña.

    Autenticación básica del navegador: protege también los enlaces directos (PDF, CSV) sin
    añadir pantallas de login. Pensada para una demo pública, no como sistema de usuarios.
    """
    if (
        settings.ACCESS_PASSWORD
        and request.url.path not in PUBLIC_PATHS
        and request.method != "OPTIONS"
        and not _authorized(request.headers.get("authorization"))
    ):
        return Response(
            "Acceso restringido",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Rekreuz", charset="UTF-8"'},
        )
    return await call_next(request)


app.include_router(vendors.router)
app.include_router(policies.router)
app.include_router(invoices.router)
app.include_router(decisions.router)
app.include_router(documents.router)
app.include_router(exchange_rates.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# Frontend compilado (despliegue en un solo servicio). Se monta al final: las rutas de la API
# tienen prioridad y todo lo demás lo sirve el frontend.
if settings.FRONTEND_DIST and settings.FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIST, html=True), name="frontend")
