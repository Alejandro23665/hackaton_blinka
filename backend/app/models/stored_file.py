import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, Column, Text
from sqlmodel import Field, SQLModel

from app.models.base import timestamp, uuid_pk
from app.models.enums import PREPROCESS_STATUSES, one_of


class StoredFile(SQLModel, table=True):
    """Archivo original tal como llegó, guardado una sola vez.

    Los bytes están en el almacenamiento de archivos (storage_key); aquí solo su referencia y su huella.
    """

    __tablename__ = "stored_files"
    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="ck_stored_files_size"),
        CheckConstraint("page_count IS NULL OR page_count >= 1", name="ck_stored_files_page_count"),
        CheckConstraint(one_of("preprocess_status", PREPROCESS_STATUSES), name="ck_stored_files_preprocess_status"),
    )

    id: uuid.UUID = uuid_pk()
    # La misma imagen enviada dos veces tiene la misma huella: no se duplica
    sha256: str = Field(min_length=64, max_length=64, unique=True)
    storage_key: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    original_name: str = Field(max_length=255)
    content_type: str = Field(max_length=50)
    size_bytes: int = Field(sa_column=Column(BigInteger, nullable=False))
    # Se conoce al convertir el archivo en páginas
    page_count: int | None = None
    preprocess_status: str = Field(default="PENDIENTE", max_length=12)
    preprocess_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = timestamp()
