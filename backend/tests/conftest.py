import os
import re

import pytest
from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.auth import create_token
from app.core.config import settings
from app.db import schema
from tests.factories import extraction, unknown_page

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def storage_dir(tmp_path, monkeypatch):
    """Cada test guarda sus archivos (y la caché de la IA) en una carpeta temporal propia."""
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path / "storage")
    monkeypatch.setattr(settings, "AI_CACHE_DIR", tmp_path / "ai_cache")
    monkeypatch.setattr(settings, "CLAUDE_KEY", "clave-de-prueba")
    # El PostgreSQL embebido de las pruebas no trae las zonas horarias con nombre
    monkeypatch.setattr(settings, "TIMEZONE", "UTC")
    return tmp_path / "storage"


class FakeAI:
    """Sustituye a la IA (client.run) y registra cada solicitud. Nunca usa la red.

    Segmentador: responde por número de página. Extractor: la primera lectura de cada documento
    responde en orden con `extractions` (o una factura correcta por defecto); la segunda
    (verificación) responde en orden con `verifications` o, si no hay, repite la primera.
    Un AIError de CUOTA, CLAVE o SIN_CLAVE hace fallar la tanda entera, como en la API real; cualquier
    otro solo esa solicitud.
    """

    STOP_CODES = ("CUOTA", "CLAVE", "SIN_CLAVE")

    def __init__(self):
        self.pages: dict[int, dict] = {}  # número de página -> respuesta del segmentador
        self.errors: dict[int, Exception] = {}  # número de página -> error a devolver
        self.calls: list[dict] = []
        self.extractions: list[dict | Exception] = []  # respuestas (o errores) del extractor, en orden
        self.extraction_calls: list[dict] = []
        self.verifications: list[dict | Exception] = []
        self.verification_calls = 0
        self.batches = 0  # tandas enviadas
        self._last_extraction: dict | None = None

    def _answer(self, request):
        if request.kind == "document_extraction" and request.reading > 1:
            self.verification_calls += 1
            return self.verifications.pop(0) if self.verifications else self._last_extraction
        if request.kind == "document_extraction":
            images = sum(1 for part in request.content if part["type"] == "image")
            self.extraction_calls.append({"prompt": request.content[0]["text"], "images": images})
            data = self.extractions.pop(0) if self.extractions else extraction()
            self._last_extraction = data
            return data
        prompt = request.content[0]["text"]
        number = int(re.search(r"Página (\d+) de", prompt).group(1))
        self.calls.append({"page": number, "prompt": prompt})
        return self.errors.get(number) or self.pages.get(number, unknown_page())

    def __call__(self, requests, progress=None):
        from decimal import Decimal

        from app.ai.client import AIError, AIResult, Call

        self.batches += 1
        results = {}
        for request in requests:
            data = self._answer(request)
            if isinstance(data, AIError) and data.code in self.STOP_CODES:
                raise data
            if isinstance(data, Exception):
                results[request.key] = data
                continue
            # Cada respuesta simulada "cuesta" 1.000 tokens de entrada y 500 de salida, en una tanda de 30 s
            call = Call("fake/modelo", f"lote{self.batches}", 1000, 500, Decimal("0.000175"), 30.0, "OK")
            results[request.key] = AIResult(data=data, parsed=request.parse(data), model="fake/modelo", calls=[call])
        return results


@pytest.fixture(autouse=True)
def fake_ai(monkeypatch):
    from app.ai import client

    fake = FakeAI()
    monkeypatch.setattr(client, "run", fake)
    return fake


@pytest.fixture(scope="session")
def engine():
    """La base de pruebas se crea con los mismos archivos db/*.sql que la real."""
    if not TEST_DATABASE_URL:
        pytest.skip("Define TEST_DATABASE_URL (una BD Postgres de pruebas) para los tests con base de datos")
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    schema.apply(TEST_DATABASE_URL, schema.sql_files())
    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(engine):
    # Los tipos, los roles y el usuario "Modelo IA" vienen de los archivos SQL: no se borran
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE llamadas_ia, documentos_procesados RESTART IDENTITY"))
        conn.execute(text("DELETE FROM usuarios WHERE email <> 'modelo-ia@sistema.local'"))
        conn.execute(text("DELETE FROM roles WHERE rol NOT IN ('MODELO', 'REVISOR', 'ADMINISTRADOR')"))
    return engine


@pytest.fixture
def session(clean_db):
    with Session(clean_db) as session:
        yield session


@pytest.fixture
def client(clean_db):
    from fastapi.testclient import TestClient

    from app.db.session import get_engine, get_session
    from app.main import app

    def override_session():
        with Session(clean_db) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_engine] = lambda: clean_db
    with TestClient(app) as test_client:
        # Sesión iniciada como un revisor (los tests de sesión usan anonymous_client)
        reviewer = create_user(clean_db, "Rita Revisora", "rita@oxxo.cl", "REVISOR")
        test_client.headers["Authorization"] = f"Bearer {create_token(reviewer)}"
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def anonymous_client(client):
    """El mismo cliente, sin sesión."""
    del client.headers["Authorization"]
    return client


PASSWORD = "clave-de-prueba-123"


def create_user(engine, name, email, role, password=PASSWORD) -> int:
    from app.auth import hash_password

    with engine.begin() as conn:
        return conn.execute(
            text(
                "INSERT INTO usuarios (nombre, email, contrasena_hash, id_rol) "
                "VALUES (:name, :email, :hash, (SELECT id FROM roles WHERE rol = :role)) RETURNING id"
            ),
            {"name": name, "email": email, "hash": hash_password(password), "role": role},
        ).scalar_one()
