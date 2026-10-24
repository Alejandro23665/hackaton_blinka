"""Archivos originales e imágenes de páginas. Solo se sirven a través de la API (con autenticación)."""
import uuid
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

from app.api.deps import SessionDep
from app.models import Page, StoredFile
from app.storage import get_storage

router = APIRouter(tags=["files"])


def _read(key: str) -> bytes:
    try:
        return get_storage().get(key)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El archivo no está en el almacenamiento") from exc


@router.get("/files/{file_id}")
def get_original(file_id: uuid.UUID, session: SessionDep):
    """El archivo original tal como llegó."""
    stored = session.get(StoredFile, file_id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archivo no encontrado")
    return Response(
        content=_read(stored.storage_key),
        media_type=stored.content_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(stored.original_name)}"},
    )


@router.get("/pages/{page_id}/image")
def get_page_image(page_id: uuid.UUID, session: SessionDep):
    """La imagen de una página tal como la ve la IA."""
    page = session.get(Page, page_id)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Página no encontrada")
    return Response(content=_read(page.image_key), media_type="image/jpeg")
