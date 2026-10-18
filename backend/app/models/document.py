from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

DOCUMENT_STATUSES = ("processing", "processed", "failed")


class Document(SQLModel, table=True):
    """Archivo de factura subido (PDF/imagen) y el resultado de la extracción del agente."""

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'processed', 'failed')", name="ck_documents_status"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    original_name: str = Field(max_length=255)
    content_type: str = Field(max_length=100)
    size_bytes: int
    # Evita procesar dos veces el mismo archivo
    sha256: str = Field(max_length=64, unique=True)
    status: str = Field(default="processing", max_length=20, index=True)
    extraction: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    invoice_id: int | None = Field(default=None, foreign_key="invoices.id", index=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
