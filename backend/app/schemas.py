"""DTOs de salida de la API (separados de las tablas)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageRead(ReadModel):
    id: uuid.UUID
    page_number: int
    width: int
    height: int
    # Resultado del segmentador-clasificador: OK, ERROR o None (pendiente)
    classification_status: str | None = None
    classification_error: str | None = None


class StoredFileRead(ReadModel):
    id: uuid.UUID
    original_name: str
    content_type: str
    size_bytes: int
    sha256: str
    page_count: int | None
    preprocess_status: str
    preprocess_error: str | None
    pages: list[PageRead] = []


class SubmissionSummary(ReadModel):
    id: uuid.UUID
    received_at: datetime
    source: str
    status: str
    file_count: int
    page_count: int


class DocumentPageRead(BaseModel):
    page_id: uuid.UUID
    file_id: uuid.UUID
    page_number: int
    index_on_page: int
    bbox: dict[str, Any] | None
    position_hint: str | None


class IssueRead(ReadModel):
    code: str
    severity: str
    field_name: str | None
    message: str


class DocumentSummary(BaseModel):
    id: uuid.UUID
    doc_type: str | None
    classification_confidence: Decimal | None
    classification_evidence: str | None
    technical_status: str
    overall_status: str | None
    review_reason: str | None
    pages: list[DocumentPageRead]
    issues: list[IssueRead]


class SubmissionRead(ReadModel):
    id: uuid.UUID
    received_at: datetime
    source: str
    status: str
    files: list[StoredFileRead]
    documents: list[DocumentSummary] = []


class SubmissionCreated(SubmissionRead):
    # Archivos repetidos que no se volvieron a guardar
    notices: list[str] = []
