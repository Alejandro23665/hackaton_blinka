"""Ajustes de despliegue: URL de la base de la nube y contraseña de acceso. No necesitan base de datos."""
import base64

from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app


def test_cloud_database_urls_use_psycopg_driver():
    assert Settings(DATABASE_URL="postgres://u:p@host:5432/db").DATABASE_URL == "postgresql+psycopg://u:p@host:5432/db"
    assert Settings(DATABASE_URL="postgresql://u:p@host/db").DATABASE_URL == "postgresql+psycopg://u:p@host/db"
    local = "postgresql+psycopg://u:p@localhost/db"
    assert Settings(DATABASE_URL=local).DATABASE_URL == local


def _basic(user: str, password: str) -> dict:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_access_password_protects_everything_but_health(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_PASSWORD", "secreto")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    denied = client.get("/policies")
    assert denied.status_code == 401 and denied.headers["www-authenticate"].startswith("Basic")
    assert client.get("/policies", headers=_basic("blinka", "otra")).status_code == 401
    assert client.get("/policies", headers={"Authorization": "Basic !!!"}).status_code == 401


def test_no_password_means_open_access(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_PASSWORD", None)
    assert TestClient(app).get("/health").status_code == 200


def test_correct_password_is_accepted(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_PASSWORD", "secreto")
    response = TestClient(app).get("/openapi.json", headers=_basic("blinka", "secreto"))
    assert response.status_code == 200
