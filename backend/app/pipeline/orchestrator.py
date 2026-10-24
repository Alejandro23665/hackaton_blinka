"""Orquestador: coordina los pasos del procesamiento de un lote.

Etapa actual: preprocesar cada archivo (páginas), segmentar y clasificar cada página con la IA y
agrupar las regiones en documentos. Los documentos desconocidos quedan terminados; los admitidos
esperan la extracción y la validación (siguientes etapas).

Cada paso es idempotente: volver a procesar un lote retoma lo que quedó pendiente o falló, sin
duplicar lo que ya estaba hecho.
"""
import logging
import uuid
from decimal import Decimal

from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.ai.client import AIError
from app.core.config import settings
from app.models import (
    Document,
    DocumentRegion,
    Page,
    PageClassification,
    ProcessingRun,
    RunIssue,
    StoredFile,
    Submission,
    SubmissionFile,
)
from app.models.base import utcnow
from app.pipeline import segmenter
from app.pipeline.grouper import GroupedDocument, group_pages
from app.pipeline.preprocess import PreprocessError, render_pages
from app.storage import get_storage, page_key

PIPELINE_VERSION = "0.2"

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


class QuotaExhausted(Exception):
    """Se agotó la cuota de la IA (o falta la clave): no tiene sentido seguir con el resto del lote."""


def _file_pages(session: Session, stored: StoredFile) -> list[Page]:
    return list(session.exec(select(Page).where(Page.file_id == stored.id).order_by(col(Page.page_number))).all())


def _current_classification(session: Session, page: Page) -> PageClassification | None:
    return session.exec(
        select(PageClassification).where(PageClassification.page_id == page.id, col(PageClassification.is_current))
    ).first()


def _already_grouped(session: Session, pages: list[Page]) -> bool:
    return session.exec(select(DocumentRegion.id).where(DocumentRegion.page_id == pages[0].id)).first() is not None


def _classify_page(session: Session, page: Page, total: int, previous: str | None) -> segmenter.PageAnalysis:
    """Clasifica una página y guarda la respuesta (o el error) en su propia transacción."""
    try:
        result = segmenter.analyze_page(get_storage().get(page.image_key), page.page_number, total, previous)
    except AIError as exc:
        session.add(
            PageClassification(
                page_id=page.id,
                is_current=False,
                status="ERROR",
                model=segmenter.model_name(),
                prompt_version=segmenter.PROMPT_VERSION,
                error=str(exc),
                attempts=0,
            )
        )
        session.commit()
        if exc.code in ("CUOTA", "SIN_CLAVE", "CLAVE"):
            raise QuotaExhausted(str(exc)) from exc
        raise
    session.add(
        PageClassification(
            page_id=page.id,
            is_current=True,
            status="OK",
            model=result.model,
            prompt_version=segmenter.PROMPT_VERSION,
            response=result.data,
            attempts=result.attempts,
            duration_ms=result.duration_ms,
        )
    )
    session.commit()
    return result.parsed


def _previous_summary(analysis: segmenter.PageAnalysis) -> str:
    last = max(analysis.documents, key=lambda d: d.index)
    return segmenter.describe(last.doc_type, last.document_number_seen)


def _save_documents(session: Session, submission: Submission, grouped: list[GroupedDocument], model: str) -> None:
    """Documentos, regiones y primer procesamiento de cada uno, todo en una transacción."""
    for item in grouped:
        document = Document(submission_id=submission.id, received_at=submission.received_at)
        session.add(document)
        session.flush()
        for position, region in enumerate(item.regions, start=1):
            session.add(
                DocumentRegion(
                    page_id=region.page_id,
                    document_id=document.id,
                    index_on_page=region.index_on_page,
                    position_in_document=position,
                    bbox=region.bbox,
                    position_hint=region.position_hint,
                )
            )
        run = ProcessingRun(
            document_id=document.id,
            run_number=1,
            pipeline_version=PIPELINE_VERSION,
            classifier_model=model,
            doc_type=item.doc_type,
            classification_confidence=Decimal(str(round(item.confidence, 3))),
            classification_evidence=item.evidence,
            total_tolerance=Decimal(settings.TOTAL_TOLERANCE_CLP),
        )
        if item.doc_type == "DESCONOCIDO":
            # Un desconocido termina aquí: se conserva la imagen y la clasificación, sin datos contables
            seen = f" (título visto: {item.evidence})" if item.evidence else " (sin título visible)"
            run.technical_status = "COMPLETADO"
            run.is_current = True
            run.finished_at = utcnow()
            run.extraction_status = "NO_APLICA"
            run.validation_status = "NO_APLICA"
            run.overall_status = "DESCONOCIDO"
            run.review_reason = "No corresponde a un tipo admitido" + seen
        session.add(run)
        session.flush()
        for issue in item.issues:
            session.add(RunIssue(run_id=run.id, **issue))
    session.commit()


def segment_file(session: Session, submission: Submission, stored: StoredFile) -> bool:
    """Clasifica las páginas que falten y, con todas listas, crea los documentos. True si terminó."""
    if stored.preprocess_status != "LISTO":
        return False
    pages = _file_pages(session, stored)
    if not pages or _already_grouped(session, pages):
        return True

    analyses: list[tuple[uuid.UUID, segmenter.PageAnalysis]] = []
    previous: str | None = None
    for page in pages:
        saved = _current_classification(session, page)
        if saved is not None:
            analysis = segmenter.PageAnalysis.model_validate(saved.response)
        else:
            try:
                analysis = _classify_page(session, page, len(pages), previous)
            except AIError:
                # Sin esta página no se sabe si la siguiente la continúa: el archivo queda pendiente
                logger.warning("No se pudo clasificar la página %s del archivo %s", page.page_number, stored.id)
                return False
        analyses.append((page.id, analysis))
        previous = _previous_summary(analysis)

    try:
        _save_documents(session, submission, group_pages(analyses), segmenter.model_name())
    except IntegrityError:
        # Otro proceso agrupó este archivo a la vez: se usa su resultado
        session.rollback()
    return True


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
        complete = True
        try:
            for stored in files:
                preprocess_file(session, stored)
                complete = segment_file(session, submission, stored) and complete
        except QuotaExhausted:
            complete = False
        except Exception:
            logger.exception("Error inesperado al procesar el lote %s", submission_id)
            session.rollback()
            complete = False

        session.refresh(submission)
        submission.status = "COMPLETADO" if complete else "COMPLETADO_CON_ERRORES"
        session.add(submission)
        session.commit()
