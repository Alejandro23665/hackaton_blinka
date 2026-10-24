import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import timestamp, uuid_pk
from app.models.enums import CALL_STATUSES, one_of


class Page(SQLModel, table=True):
    """Una página de un archivo, ya convertida en imagen. Es lo que ve la IA.

    Un JPG es una página; un PDF de 5 páginas son 5.
    """

    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("file_id", "page_number", name="uq_pages_file_page"),
        CheckConstraint("page_number >= 1", name="ck_pages_page_number"),
    )

    id: uuid.UUID = uuid_pk()
    file_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("stored_files.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    page_number: int
    # Imagen preparada: orientación corregida y tamaño limitado
    image_key: str = Field(sa_column=Column(Text, nullable=False))
    width: int
    height: int
    created_at: datetime = timestamp()


class PageClassification(SQLModel, table=True):
    """Respuesta del segmentador-clasificador para una página: qué documentos ve y de qué tipo.

    Se guarda la respuesta original de la IA para auditoría. Si se vuelve a clasificar, la anterior
    queda en el historial y solo una es la actual.
    """

    __tablename__ = "page_classifications"
    __table_args__ = (
        CheckConstraint(one_of("status", CALL_STATUSES), name="ck_page_classifications_status"),
        Index(
            "uq_page_classifications_current",
            "page_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: uuid.UUID = uuid_pk()
    page_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("pages.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    is_current: bool = True
    status: str = Field(max_length=10)
    model: str = Field(max_length=100)
    prompt_version: str = Field(max_length=20)
    response: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    attempts: int = 1
    duration_ms: int | None = None
    created_at: datetime = timestamp()
