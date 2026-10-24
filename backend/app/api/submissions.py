import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.api.documents import shown_run
from app.models import (
    DocumentRegion,
    Page,
    PageClassification,
    ProcessingRun,
    RunIssue,
    StoredFile,
    Submission,
    SubmissionFile,
)
from app.pipeline import intake
from app.pipeline.orchestrator import process_submission, reset_file
from app.schemas import (
    DocumentPageRead,
    DocumentSummary,
    IssueRead,
    PageRead,
    StoredFileRead,
    SubmissionCreated,
    SubmissionRead,
    SubmissionSummary,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _detail(session: Session, submission: Submission) -> SubmissionRead:
    files = session.exec(
        select(StoredFile)
        .join(SubmissionFile, col(SubmissionFile.file_id) == StoredFile.id)
        .where(SubmissionFile.submission_id == submission.id)
        .order_by(col(SubmissionFile.position))
    ).all()
    pages: dict[uuid.UUID, list[Page]] = {f.id: [] for f in files}
    if files:
        for page in session.exec(
            select(Page).where(col(Page.file_id).in_(list(pages))).order_by(col(Page.page_number))
        ).all():
            pages[page.file_id].append(page)
    all_pages = {p.id: p for file_pages in pages.values() for p in file_pages}
    classifications = _latest_classifications(session, list(all_pages))

    def page_read(page: Page) -> PageRead:
        found = classifications.get(page.id)
        return PageRead.model_validate(page).model_copy(
            update={
                "classification_status": found.status if found else None,
                "classification_error": found.error if found else None,
            }
        )

    return SubmissionRead(
        id=submission.id,
        received_at=submission.received_at,
        source=submission.source,
        status=submission.status,
        files=[
            StoredFileRead.model_validate(f).model_copy(update={"pages": [page_read(p) for p in pages[f.id]]})
            for f in files
        ],
        documents=_documents(session, all_pages, {f.id: i for i, f in enumerate(files)}),
    )


def _latest_classifications(session: Session, page_ids: list[uuid.UUID]) -> dict[uuid.UUID, PageClassification]:
    """La clasificación actual de cada página o, si no hay, el último intento fallido."""
    found: dict[uuid.UUID, PageClassification] = {}
    if page_ids:
        for item in session.exec(
            select(PageClassification)
            .where(col(PageClassification.page_id).in_(page_ids))
            .order_by(col(PageClassification.created_at))
        ).all():
            current = found.get(item.page_id)
            if current is None or not current.is_current:
                found[item.page_id] = item
    return found


def _documents(
    session: Session, pages: dict[uuid.UUID, Page], file_order: dict[uuid.UUID, int]
) -> list[DocumentSummary]:
    """Documentos que aparecen en las páginas del lote, en orden de aparición, con su último procesamiento."""
    if not pages:
        return []
    regions = session.exec(select(DocumentRegion).where(col(DocumentRegion.page_id).in_(list(pages)))).all()
    by_document: dict[uuid.UUID, list[DocumentRegion]] = {}
    for region in regions:
        by_document.setdefault(region.document_id, []).append(region)
    if not by_document:
        return []

    all_runs: dict[uuid.UUID, list[ProcessingRun]] = {}
    for run in session.exec(
        select(ProcessingRun).where(col(ProcessingRun.document_id).in_(list(by_document)))
    ).all():
        all_runs.setdefault(run.document_id, []).append(run)
    runs = {document_id: shown_run(items) for document_id, items in all_runs.items()}
    issues: dict[uuid.UUID, list[RunIssue]] = {}
    if runs:
        for issue in session.exec(
            select(RunIssue).where(col(RunIssue.run_id).in_([r.id for r in runs.values()]))
        ).all():
            issues.setdefault(issue.run_id, []).append(issue)

    def first_page(item: tuple[uuid.UUID, list[DocumentRegion]]):
        region = min(item[1], key=lambda r: r.position_in_document)
        page = pages[region.page_id]
        return (file_order[page.file_id], page.page_number, region.index_on_page)

    result = []
    for document_id, doc_regions in sorted(by_document.items(), key=first_page):
        run = runs.get(document_id)
        result.append(
            DocumentSummary(
                id=document_id,
                doc_type=run.doc_type if run else None,
                classification_confidence=run.classification_confidence if run else None,
                classification_evidence=run.classification_evidence if run else None,
                technical_status=run.technical_status if run else "EN_PROCESO",
                overall_status=run.overall_status if run else None,
                review_reason=run.review_reason if run else None,
                provider_rut=run.provider_rut if run else None,
                rut_is_substitute=run.rut_is_substitute if run else False,
                document_number=run.document_number if run else None,
                issue_date=run.issue_date if run else None,
                total_amount=run.total_amount if run else None,
                has_signature=run.has_signature if run else None,
                pages=[
                    DocumentPageRead(
                        page_id=r.page_id,
                        file_id=pages[r.page_id].file_id,
                        page_number=pages[r.page_id].page_number,
                        index_on_page=r.index_on_page,
                        bbox=r.bbox,
                        position_hint=r.position_hint,
                    )
                    for r in sorted(doc_regions, key=lambda r: r.position_in_document)
                ],
                issues=[IssueRead.model_validate(i) for i in issues.get(run.id, [])] if run else [],
            )
        )
    return result


@router.post("", response_model=SubmissionCreated, status_code=status.HTTP_201_CREATED)
def create_submission(session: SessionDep, background: BackgroundTasks, files: list[UploadFile] = File(...)):
    """Recibe un lote (una o varias imágenes o PDF). Responde al instante y procesa en segundo plano.

    El progreso se consulta con GET /submissions/{id}.
    """
    uploads = [intake.Upload(name=f.filename or "archivo", data=f.file.read()) for f in files]
    try:
        received = intake.receive(session, uploads)
    except intake.InvalidUpload as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    background.add_task(process_submission, session.get_bind(), received.submission.id)
    detail = _detail(session, received.submission)
    return SubmissionCreated(**detail.model_dump(), notices=received.notices)


@router.get("", response_model=list[SubmissionSummary])
def list_submissions(session: SessionDep, limit: int = Query(default=50, ge=1, le=200)):
    file_count = func.count(func.distinct(SubmissionFile.file_id))
    page_count = func.count(Page.id)
    rows = session.exec(
        select(Submission, file_count, page_count)
        .join(SubmissionFile, col(SubmissionFile.submission_id) == Submission.id, isouter=True)
        .join(Page, col(Page.file_id) == SubmissionFile.file_id, isouter=True)
        .group_by(col(Submission.id))
        .order_by(col(Submission.received_at).desc())
        .limit(limit)
    ).all()
    return [
        SubmissionSummary(
            id=s.id, received_at=s.received_at, source=s.source, status=s.status, file_count=files, page_count=pages
        )
        for s, files, pages in rows
    ]


def _get_or_404(session: Session, submission_id: uuid.UUID) -> Submission:
    submission = session.get(Submission, submission_id)
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lote no encontrado")
    return submission


@router.get("/{submission_id}", response_model=SubmissionRead)
def get_submission(submission_id: uuid.UUID, session: SessionDep):
    return _detail(session, _get_or_404(session, submission_id))


@router.post("/{submission_id}/process", response_model=SubmissionRead, status_code=status.HTTP_202_ACCEPTED)
def reprocess_submission(submission_id: uuid.UUID, session: SessionDep, background: BackgroundTasks):
    """Vuelve a procesar un lote: retoma lo pendiente y reintenta lo que falló (lo hecho no se repite)."""
    submission = _get_or_404(session, submission_id)
    background.add_task(process_submission, session.get_bind(), submission.id)
    return _detail(session, submission)


@router.post(
    "/{submission_id}/files/{file_id}/reclassify",
    response_model=SubmissionRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def reclassify_file(submission_id: uuid.UUID, file_id: uuid.UUID, session: SessionDep, background: BackgroundTasks):
    """Vuelve a clasificar un archivo del lote desde cero (por ejemplo, tras mejorar las instrucciones).

    Sus documentos actuales se eliminan y se crean de nuevo; las clasificaciones anteriores de sus
    páginas quedan en el historial.
    """
    submission = _get_or_404(session, submission_id)
    in_lot = session.exec(
        select(SubmissionFile).where(SubmissionFile.submission_id == submission_id, SubmissionFile.file_id == file_id)
    ).first()
    stored = session.get(StoredFile, file_id)
    if in_lot is None or stored is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "El archivo no pertenece a este lote")
    if submission.status in ("RECIBIDO", "EN_PROCESO"):
        raise HTTPException(status.HTTP_409_CONFLICT, "El lote se está procesando; espera a que termine")
    reset_file(session, stored)
    submission.status = "EN_PROCESO"
    session.add(submission)
    session.commit()
    background.add_task(process_submission, session.get_bind(), submission.id)
    return _detail(session, submission)
