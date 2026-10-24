import os
import re

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.core.config import settings
from tests.factories import unknown_page

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def storage_dir(tmp_path, monkeypatch):
    """Cada test guarda sus archivos (y la caché de la IA) en una carpeta temporal propia."""
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(settings, "AI_CACHE_DIR", tmp_path / "ai_cache")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "clave-de-prueba")
    return tmp_path / "storage"


class FakeAI:
    """Sustituye al modelo: responde por número de página y registra cada llamada. Nunca usa la red."""

    def __init__(self):
        self.pages: dict[int, dict] = {}  # número de página -> respuesta del segmentador
        self.errors: dict[int, Exception] = {}  # número de página -> error a lanzar
        self.calls: list[dict] = []

    def __call__(self, *, system, content, schema, schema_name, model, parse):
        from app.ai.client import AIResult

        prompt = content[0]["text"]
        number = int(re.search(r"Página (\d+) de", prompt).group(1))
        self.calls.append({"page": number, "prompt": prompt, "schema_name": schema_name})
        if number in self.errors:
            raise self.errors[number]
        data = self.pages.get(number, unknown_page())
        return AIResult(data=data, parsed=parse(data), model="fake/modelo", attempts=1, duration_ms=5)


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    from app.ai import client

    fake = FakeAI()
    monkeypatch.setattr(client, "call_json", fake)
    return fake


@pytest.fixture(scope="session")
def engine():
    if not TEST_DATABASE_URL:
        pytest.skip("Define TEST_DATABASE_URL (una BD Postgres de pruebas) para los tests con base de datos")
    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def clean_db(engine):
    tables = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    return engine


@pytest.fixture
def session(clean_db):
    with Session(clean_db) as session:
        yield session


@pytest.fixture
def client(clean_db):
    from fastapi.testclient import TestClient

    from app.db.session import get_session
    from app.main import app

    def override_session():
        with Session(clean_db) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
