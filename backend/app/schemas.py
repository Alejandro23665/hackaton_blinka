"""DTOs de salida de la API (separados de las tablas)."""
import uuid
from datetime import date, datetime
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
    provider_rut: str | None = None
    rut_is_substitute: bool = False
    document_number: str | None = None
    issue_date: date | None = None
    total_amount: Decimal | None = None
    has_signature: bool | None = None
    pages: list[DocumentPageRead]
    issues: list[IssueRead]


class FieldRead(ReadModel):
    field_name: str
    status: str
    is_required: bool
    raw_text: str | None
    confidence: Decimal | None
    region_id: uuid.UUID | None
    invalid_reason: str | None


class StepRead(ReadModel):
    step: str
    status: str
    attempts: int
    model: str | None
    duration_ms: int | None
    cost_usd: Decimal | None
    error_message: str | None
    created_at: datetime


class RunRead(ReadModel):
    id: uuid.UUID
    run_number: int
    is_current: bool
    technical_status: str
    started_at: datetime
    finished_at: datetime | None
    pipeline_version: str
    classifier_model: str | None
    extractor_model: str | None
    error_code: str | None
    error_message: str | None
    doc_type: str | None
    classification_confidence: Decimal | None
    classification_evidence: str | None
    extraction_status: str | None
    validation_status: str | None
    overall_status: str | None
    review_reason: str | None
    provider_rut: str | None
    rut_is_substitute: bool
    document_number: str | None
    issue_date: date | None
    net_amount: Decimal | None
    tax_amount: Decimal | None
    vat_amount: Decimal | None
    exempt_amount: Decimal | None
    total_amount: Decimal | None
    calculated_total: Decimal | None
    difference: Decimal | None
    total_tolerance: Decimal
    has_signature: bool | None
    signature_confidence: Decimal | None
    ocr_text: str | None


class RegionRead(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    file_id: uuid.UUID
    page_number: int
    index_on_page: int
    bbox: dict[str, Any] | None
    position_hint: str | None
    has_crop: bool


class RunSummary(ReadModel):
    run_number: int
    is_current: bool
    technical_status: str
    overall_status: str | None
    started_at: datetime
    finished_at: datetime | None


class DocumentListItem(BaseModel):
    id: uuid.UUID
    submission_id: uuid.UUID
    received_at: datetime
    doc_type: str | None
    technical_status: str
    overall_status: str | None
    provider_rut: str | None
    rut_is_substitute: bool
    document_number: str | None
    issue_date: date | None
    total_amount: Decimal | None
    difference: Decimal | None
    review_reason: str | None
    has_signature: bool | None
    issue_count: int
    first_page_id: uuid.UUID | None


class DocumentStats(BaseModel):
    total: int
    # Por estado general (o técnico si aún no termina: EN_PROCESO, FALLIDO)
    by_status: dict[str, int]
    by_type: dict[str, int]


class DocumentDetail(BaseModel):
    """Un documento con su procesamiento más reciente y todo lo necesario para auditarlo."""

    id: uuid.UUID
    submission_id: uuid.UUID
    received_at: datetime
    regions: list[RegionRead]
    run: RunRead | None
    fields: list[FieldRead]
    issues: list[IssueRead]
    steps: list[StepRead]
    history: list[RunSummary]


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
