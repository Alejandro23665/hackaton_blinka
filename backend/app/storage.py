"""Almacenamiento de archivos (originales e imágenes de páginas).

La base de datos guarda solo la clave de cada archivo. Hoy se guardan en una carpeta (en producción,
un volumen persistente); cambiar a un almacenamiento tipo S3 (Cloudflare R2…) es escribir otra
clase con los mismos métodos.
"""
import re
from pathlib import Path
from typing import Protocol

from app.core.config import settings

# Claves generadas por el propio sistema: letras, números, guiones y barras. Nunca "..".
_SAFE_KEY = re.compile(r"^[A-Za-z0-9_\-]+(/[A-Za-z0-9_\-]+)*\.[a-z0-9]+$")


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.match(key):
            raise ValueError(f"Clave de almacenamiento no válida: {key!r}")
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Se escribe aparte y se renombra: nunca queda un archivo a medio escribir con el nombre final
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


def get_storage() -> Storage:
    return LocalStorage(settings.STORAGE_DIR)


def original_key(sha256: str, extension: str) -> str:
    """El original se guarda por su huella: el mismo archivo siempre cae en la misma clave."""
    return f"originals/{sha256[:2]}/{sha256}{extension}"


def page_key(sha256: str, page_number: int) -> str:
    return f"pages/{sha256[:2]}/{sha256}/{page_number:04d}.jpg"
