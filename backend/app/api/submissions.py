import uuid

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.models import Page, StoredFile, Submission, SubmissionFile
from app.pipeline import intake
from app.pipeline.orchestrator import process_submission
from app.schemas import PageRead, StoredFileRead, SubmissionCreated, SubmissionRead, SubmissionSummary

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
    return SubmissionRead(
        id=submission.id,
        received_at=submission.received_at,
        source=submission.source,
        status=submission.status,
        files=[
            StoredFileRead.model_validate(f).model_copy(
                update={"pages": [PageRead.model_validate(p) for p in pages[f.id]]}
            )
            for f in files
        ],
    )


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
