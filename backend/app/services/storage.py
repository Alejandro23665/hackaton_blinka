"""Tipo y huella de los archivos de facturas.

El tipo se detecta por el contenido, no por la extensión ni por el Content-Type de la petición.
El contenido se guarda en Postgres (tabla document_files), no en disco.
"""
import hashlib

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
