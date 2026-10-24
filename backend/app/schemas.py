"""DTOs de salida de la API (separados de las tablas)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageRead(ReadModel):
    id: uuid.UUID
    page_number: int
    width: int
    height: int


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


class SubmissionRead(ReadModel):
    id: uuid.UUID
    received_at: datetime
    source: str
    status: str
    files: list[StoredFileRead]


class SubmissionCreated(SubmissionRead):
    # Archivos repetidos que no se volvieron a guardar
    notices: list[str] = []
