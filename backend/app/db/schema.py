"""La base de datos se define en los archivos SQL de la carpeta db/ (001_..., 002_..., en orden).

    python -m app.db.schema              # crea las tablas si la base está vacía
    python -m app.db.schema db/005_x.sql # aplica un archivo nuevo a una base que ya existe

No hay tabla de control de versiones: cada archivo nuevo se aplica una vez, a mano, en las bases
que ya existían. Una base vacía recibe todos los archivos en orden.
"""
import sys
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from app.core.config import BACKEND_DIR, settings

SQL_DIR = BACKEND_DIR.parent / "db"


def sql_files() -> list[Path]:
    return sorted(SQL_DIR.glob("*.sql"))


def _connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False))


def apply(database_url: str, files: list[Path]) -> None:
    """Aplica los archivos en orden, todos en una transacción: o quedan todos o ninguno."""
    with _connect(database_url) as conn:
        for path in files:
            conn.execute(path.read_text(encoding="utf-8"))


def is_empty(database_url: str) -> bool:
    with _connect(database_url) as conn:
        return conn.execute("SELECT to_regclass('public.documentos_procesados') IS NULL").fetchone()[0]


def ensure_schema(database_url: str) -> bool:
    """Crea las tablas si la base está vacía. True si las creó."""
    if not is_empty(database_url):
        return False
    apply(database_url, sql_files())
    return True


def main() -> None:
    if len(sys.argv) > 1:
        files = [Path(arg).resolve() for arg in sys.argv[1:]]
        apply(settings.DATABASE_URL, files)
        print("Aplicado:", ", ".join(p.name for p in files))
    elif ensure_schema(settings.DATABASE_URL):
        print("Tablas creadas:", ", ".join(p.name for p in sql_files()))
    else:
        print("La base ya tiene las tablas: no se cambió nada.")


if __name__ == "__main__":
    main()
