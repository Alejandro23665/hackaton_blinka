"""Guardado local de los archivos de facturas.

Los archivos se nombran por su hash (no por el nombre que envía el usuario) y el tipo se detecta
por su contenido, no por la extensión ni por el Content-Type de la petición.
"""
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings

# firma inicial -> (content_type, extensión)
_SIGNATURES = [
    (b"%PDF-", ("application/pdf", ".pdf")),
    (b"\x89PNG\r\n\x1a\n", ("image/png", ".png")),
    (b"\xff\xd8\xff", ("image/jpeg", ".jpg")),
]

ALLOWED_DESCRIPTION = "PDF, PNG, JPG o WEBP"


class UnsupportedFile(ValueError):
    pass


def detect_type(data: bytes) -> tuple[str, str]:
    for signature, kind in _SIGNATURES:
        if data.startswith(signature):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise UnsupportedFile(f"Formato no soportado. Sube un archivo {ALLOWED_DESCRIPTION}.")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(data: bytes, digest: str, extension: str) -> str:
    """Escribe el archivo y devuelve su ruta relativa a STORAGE_DIR (con '/')."""
    now = datetime.now(UTC)
    relative = Path("invoices", f"{now:%Y}", f"{now:%m}", f"{digest[:16]}{extension}")
    target = settings.STORAGE_DIR / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return relative.as_posix()


def resolve(relative: str) -> Path:
    """Ruta absoluta de un archivo guardado, sin permitir salir de STORAGE_DIR."""
    root = settings.STORAGE_DIR.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Ruta fuera del almacenamiento")
    return path
