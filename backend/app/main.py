from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import decisions, invoices, policies, vendors

app = FastAPI(title="Blinka API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vendors.router)
app.include_router(policies.router)
app.include_router(invoices.router)
app.include_router(decisions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
