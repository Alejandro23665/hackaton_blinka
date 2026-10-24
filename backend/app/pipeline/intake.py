"""Recepción de un lote: valida los archivos, guarda los originales y crea los registros.

Va en su propia transacción y antes de cualquier procesamiento: aunque después falle todo,
los originales quedan guardados y el lote se puede reprocesar.
"""
import hashlib
from dataclasses import dataclass, field

from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import StoredFile, Submission, SubmissionFile
from app.pipeline.preprocess import detect_type
from app.storage import get_storage, original_key


class InvalidUpload(ValueError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Upload:
    name: str
    data: bytes


@dataclass
class ReceivedSubmission:
    submission: Submission
    # Avisos para quien sube: archivos repetidos que no se vuelven a guardar
    notices: list[str] = field(default_factory=list)


def _validate(uploads: list[Upload]) -> list[tuple[Upload, str, str, str]]:
    """Comprueba todo antes de guardar nada: un archivo inválido rechaza el lote entero."""
    if not uploads:
        raise InvalidUpload("El lote no trae archivos", 422)
    if len(uploads) > settings.MAX_FILES_PER_SUBMISSION:
        raise InvalidUpload(f"Máximo {settings.MAX_FILES_PER_SUBMISSION} archivos por lote", 422)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    checked = []
    for upload in uploads:
        if not upload.data:
            raise InvalidUpload(f"'{upload.name}' está vacío", 422)
        if len(upload.data) > max_bytes:
            raise InvalidUpload(f"'{upload.name}' supera el máximo de {settings.MAX_UPLOAD_MB} MB", 413)
        try:
            content_type, extension = detect_type(upload.data)
        except ValueError as exc:
            raise InvalidUpload(f"'{upload.name}': {exc}", 415) from exc
        checked.append((upload, content_type, extension, hashlib.sha256(upload.data).hexdigest()))
    return checked


def receive(session: Session, uploads: list[Upload], source: str = "UPLOAD") -> ReceivedSubmission:
    checked = _validate(uploads)
    storage = get_storage()
    submission = Submission(source=source)
    session.add(submission)
    # Sin relaciones ORM, SQLAlchemy no ordena los INSERT por claves foráneas: se insertan en orden
    session.flush()
    received = ReceivedSubmission(submission)
    seen: set[str] = set()

    for upload, content_type, extension, sha in checked:
        if sha in seen:
            received.notices.append(f"'{upload.name}' venía repetido en este lote; se guardó una sola vez.")
            continue
        seen.add(sha)

        stored = session.exec(select(StoredFile).where(StoredFile.sha256 == sha)).first()
        if stored is None:
            key = original_key(sha, extension)
            stored = StoredFile(
                sha256=sha,
                storage_key=key,
                original_name=upload.name[:255],
                content_type=content_type,
                size_bytes=len(upload.data),
            )
            session.add(stored)
            session.flush()
            storage.put(key, upload.data)
        else:
            first = session.exec(
                select(Submission)
                .join(SubmissionFile, col(SubmissionFile.submission_id) == Submission.id)
                .where(SubmissionFile.file_id == stored.id)
                .order_by(col(Submission.received_at))
            ).first()
            when = f" el {first.received_at:%d-%m-%Y %H:%M}" if first else ""
            received.notices.append(
                f"'{upload.name}' ya se había recibido{when} (como '{stored.original_name}'); no se vuelve a guardar."
            )
            # Si el original se perdió del almacenamiento, se repone con esta copia idéntica
            if not storage.exists(stored.storage_key):
                storage.put(stored.storage_key, upload.data)

        session.add(SubmissionFile(submission_id=submission.id, file_id=stored.id, position=len(seen)))

    session.commit()
    session.refresh(submission)
    return received
