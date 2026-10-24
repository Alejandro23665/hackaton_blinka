import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, ForeignKey, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import timestamp, uuid_pk


class Document(SQLModel, table=True):
    """Un documento lógico: una guía, un control interno, una factura… o algo desconocido.

    Tiene pocos campos a propósito: los resultados están en processing_runs, para poder reprocesar
    sin tocar el documento ni duplicar la imagen.
    """

    __tablename__ = "documents"

    id: uuid.UUID = uuid_pk()
    submission_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    # Fecha de recepción (la del lote)
    received_at: datetime = timestamp()
    created_at: datetime = timestamp()


class DocumentRegion(SQLModel, table=True):
    """Un documento dentro de una página: la página entera o una zona (dos facturas en una foto).

    Una factura de 3 páginas son 3 regiones de un documento; una foto con 2 facturas son 2 regiones
    de documentos distintos.
    """

    __tablename__ = "document_regions"
    __table_args__ = (
        UniqueConstraint("page_id", "index_on_page", name="uq_document_regions_page_index"),
        UniqueConstraint("document_id", "position_in_document", name="uq_document_regions_position"),
        CheckConstraint("index_on_page >= 1", name="ck_document_regions_index"),
        CheckConstraint("position_in_document >= 1", name="ck_document_regions_position"),
    )

    id: uuid.UUID = uuid_pk()
    page_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    document_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    index_on_page: int
    position_in_document: int
    # Zona aproximada en proporciones 0–1 {x, y, w, h}; nulo = página completa
    bbox: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    crop_key: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    position_hint: str | None = Field(default=None, max_length=100)
