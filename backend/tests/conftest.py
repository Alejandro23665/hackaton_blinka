import os

import pytest
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401
from app.core.config import settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@pytest.fixture(autouse=True)
def storage_dir(tmp_path, monkeypatch):
    """Cada test guarda sus archivos en una carpeta temporal propia."""
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path / "storage")
    return tmp_path / "storage"


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
