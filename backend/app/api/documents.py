from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.core.config import settings
from app.models import Document, DocumentFile
from app.schemas import DocumentRead, TextDocumentCreate
from app.services import documents, storage

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_document(session: SessionDep, file: UploadFile = File(...)):
    """Sube una factura (PDF o imagen). El agente extrae los datos, crea la factura y la evalúa.

    Si la lectura falla, el documento queda guardado con status 'failed' y el motivo en 'error'.
    """
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    data = file.file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El archivo está vacío")
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, f"El archivo supera {settings.MAX_UPLOAD_MB} MB"
        )

    try:
        return documents.process_upload(session, data, file.filename or "factura")
    except storage.UnsupportedFile as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except documents.DuplicateDocument as exc:
        existing = exc.document
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Este archivo ya se subió como '{existing.original_name}' (documento {existing.id}).",
        ) from exc


@router.post("/text", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload_text(payload: TextDocumentCreate, session: SessionDep):
    """Factura recibida por correo o chat: se pega su texto y sigue el mismo flujo que un archivo."""
    label = "correo" if payload.source == "email" else "chat"
    name = f"{label}-{datetime.now(UTC):%Y%m%d-%H%M%S}.txt"
    try:
        return documents.process_upload(session, payload.text.strip().encode("utf-8"), name, is_text=True)
    except documents.DuplicateDocument as exc:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Este texto ya se envió antes (documento {exc.document.id})."
        ) from exc


@router.get("", response_model=list[DocumentRead])
def list_documents(session: SessionDep, limit: int = 20):
    query = (
        select(Document)
        .order_by(col(Document.created_at).desc(), col(Document.id).desc())
        .limit(min(limit, 200))
    )
    return session.exec(query).all()


def _get_or_404(session: SessionDep, document_id: int) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return document


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: int, session: SessionDep):
    return _get_or_404(session, document_id)


@router.get("/{document_id}/file")
def get_document_file(document_id: int, session: SessionDep):
    """Devuelve el archivo original para verlo en el navegador."""
    document = _get_or_404(session, document_id)
    stored = session.get(DocumentFile, document_id)
    if stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El archivo original no está guardado")
    # charset explícito para que tildes y eñes del texto pegado se vean bien
    media_type = "text/plain; charset=utf-8" if document.content_type == "text/plain" else document.content_type
    return Response(
        content=stored.content,
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(document.original_name)}"},
    )
