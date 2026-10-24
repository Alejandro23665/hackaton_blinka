"""Orquestador: coordina los pasos del procesamiento de un lote.

Etapa actual: preprocesar cada archivo (convertirlo en páginas). La clasificación, extracción y
validación se añaden en las siguientes etapas.

Cada paso es idempotente: volver a procesar un lote retoma lo que quedó pendiente o falló, sin
duplicar lo que ya estaba hecho.
"""
import logging
import uuid

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import Page, StoredFile, Submission, SubmissionFile
from app.pipeline.preprocess import PreprocessError, render_pages
from app.storage import get_storage, page_key

logger = logging.getLogger(__name__)


def _submission_files(session: Session, submission_id: uuid.UUID) -> list[StoredFile]:
    return list(
        session.exec(
            select(StoredFile)
            .join(SubmissionFile, col(SubmissionFile.file_id) == StoredFile.id)
            .where(SubmissionFile.submission_id == submission_id)
            .order_by(col(SubmissionFile.position))
        ).all()
    )


def preprocess_file(session: Session, stored: StoredFile) -> None:
    """Convierte el archivo en páginas. Las páginas y el estado LISTO se guardan juntos o nada."""
    if stored.preprocess_status == "LISTO":
        return
    storage = get_storage()
    try:
        pages = render_pages(storage.get(stored.storage_key), stored.content_type)
        for page in pages:
            key = page_key(stored.sha256, page.number)
            storage.put(key, page.data)
            session.add(
                Page(file_id=stored.id, page_number=page.number, image_key=key, width=page.width, height=page.height)
            )
        stored.page_count = len(pages)
        stored.preprocess_status = "LISTO"
        stored.preprocess_error = None
        session.add(stored)
        session.commit()
    except IntegrityError:
        # Otro lote con el mismo archivo lo preprocesó a la vez: se usa su resultado
        session.rollback()
        session.refresh(stored)
    except PreprocessError as exc:
        session.rollback()
        _mark_failed(session, stored, str(exc))
    except Exception as exc:  # el original queda guardado y el lote se puede reprocesar
        logger.exception("Error inesperado al preprocesar el archivo %s", stored.id)
        session.rollback()
        _mark_failed(session, stored, f"Error inesperado: {exc}")


def _mark_failed(session: Session, stored: StoredFile, message: str) -> None:
    session.refresh(stored)
    stored.preprocess_status = "FALLIDO"
    stored.preprocess_error = message
    session.add(stored)
    session.commit()


def process_submission(engine: Engine, submission_id: uuid.UUID) -> None:
    """Procesa un lote en segundo plano, con su propia sesión de base de datos."""
    with Session(engine) as session:
        submission = session.get(Submission, submission_id)
        if submission is None:
            return
        submission.status = "EN_PROCESO"
        session.add(submission)
        session.commit()

        files = _submission_files(session, submission_id)
        for stored in files:
            preprocess_file(session, stored)

        session.refresh(submission)
        failed = any(f.preprocess_status != "LISTO" for f in files)
        submission.status = "COMPLETADO_CON_ERRORES" if failed else "COMPLETADO"
        session.add(submission)
        session.commit()

