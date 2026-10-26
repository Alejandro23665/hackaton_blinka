"""Ajustes de despliegue: URL de la base de la nube. No necesitan base de datos."""
from app.core.config import Settings


def test_cloud_database_urls_use_psycopg_driver():
    assert Settings(DATABASE_URL="postgres://u:p@host:5432/db").DATABASE_URL == "postgresql+psycopg://u:p@host:5432/db"
    assert Settings(DATABASE_URL="postgresql://u:p@host/db").DATABASE_URL == "postgresql+psycopg://u:p@host/db"
    local = "postgresql+psycopg://u:p@localhost/db"
    assert Settings(DATABASE_URL=local).DATABASE_URL == local
