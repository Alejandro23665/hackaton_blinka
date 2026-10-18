from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import decisions, documents, exchange_rates, invoices, policies, vendors
from app.core.config import settings

app = FastAPI(title="Blinka API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vendors.router)
app.include_router(policies.router)
app.include_router(invoices.router)
app.include_router(decisions.router)
app.include_router(documents.router)
app.include_router(exchange_rates.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
