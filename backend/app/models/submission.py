import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, ForeignKey, Text, UniqueConstraint, Uuid
from sqlmodel import Field, SQLModel

from app.models.base import timestamp, uuid_pk
from app.models.enums import SUBMISSION_SOURCES, SUBMISSION_STATUSES, one_of


class Submission(SQLModel, table=True):
    """Un lote: todo lo que se sube de una vez (uno o varios archivos)."""

    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint(one_of("source", SUBMISSION_SOURCES), name="ck_submissions_source"),
        CheckConstraint(one_of("status", SUBMISSION_STATUSES), name="ck_submissions_status"),
    )

    id: uuid.UUID = uuid_pk()
    # Fecha de recepción de todos los documentos del lote
    received_at: datetime = timestamp()
    source: str = Field(default="UPLOAD", max_length=20)
    status: str = Field(default="RECIBIDO", max_length=30, index=True)
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class SubmissionFile(SQLModel, table=True):
    """Qué archivos trae cada lote. Un mismo archivo puede llegar en varios lotes sin guardarse dos veces."""

    __tablename__ = "submission_files"
    __table_args__ = (UniqueConstraint("submission_id", "position", name="uq_submission_files_position"),)

    submission_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("submissions.id", ondelete="CASCADE"), primary_key=True)
    )
    file_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("stored_files.id", ondelete="RESTRICT"), primary_key=True)
    )
    position: int
