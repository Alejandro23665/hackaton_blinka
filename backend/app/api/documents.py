import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import aliased
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.models import Document, DocumentRegion, ExtractedField, Page, ProcessingRun, RunIssue, RunStep
from app.models.enums import FIELD_NAMES
from app.pipeline.orchestrator import new_run_from, process_single_document
from app.schemas import (
    DocumentDetail,
    DocumentListItem,
    DocumentStats,
    FieldRead,
    IssueRead,
    RegionRead,
    RunRead,
    RunSummary,
    StepRead,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def shown_run(runs: list[ProcessingRun]) -> ProcessingRun | None:
    """El procesamiento que se muestra: el actual; si aún no hay, el más reciente (en curso o fallido)."""
    current = [r for r in runs if r.is_current]
    return current[0] if current else (max(runs, key=lambda r: r.run_number) if runs else None)


def _shown_runs():
    """Subconsulta: el procesamiento que se muestra de cada documento (el actual o el más reciente)."""
    return (
        select(ProcessingRun)
        .ext(distinct_on(col(ProcessingRun.document_id)))
        .order_by(
            col(ProcessingRun.document_id), col(ProcessingRun.is_current).desc(), col(ProcessingRun.run_number).desc()
        )
        .subquery()
    )


def _status(run) -> str:
    return run.overall_status or run.technical_status


@router.get("", response_model=list[DocumentListItem])
def list_documents(
    session: SessionDep,
    status_filter: str | None = Query(
        default=None,
        alias="status",
        description="PROCESADO, NO_LEGIBLE, DESCUADRE, DESCONOCIDO, EN_PROCESO o FALLIDO",
    ),
    doc_type: str | None = None,
    q: str | None = Query(default=None, description="Busca por RUT o número de documento"),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Bandeja de documentos, del más reciente al más antiguo, con su resultado vigente."""
    runs = aliased(ProcessingRun, _shown_runs())
    query = select(Document, runs).join(runs, col(runs.document_id) == Document.id)
    if status_filter in ("EN_PROCESO", "FALLIDO"):
        query = query.where(col(runs.overall_status).is_(None), runs.technical_status == status_filter)
    elif status_filter:
        query = query.where(runs.overall_status == status_filter)
    if doc_type:
        query = query.where(runs.doc_type == doc_type)
    if q and q.strip():
        pattern = f"%{q.strip().replace('.', '')}%"
        query = query.where(or_(col(runs.provider_rut).ilike(pattern), col(runs.document_number).ilike(pattern)))
    rows = session.exec(query.order_by(col(Document.received_at).desc(), col(Document.created_at)).limit(limit)).all()

    document_ids = [d.id for d, _ in rows]
    issue_counts: dict[uuid.UUID, int] = {}
    first_pages: dict[uuid.UUID, uuid.UUID] = {}
    if rows:
        run_ids = [r.id for _, r in rows]
        for run_id, count in session.exec(
            select(RunIssue.run_id, func.count()).where(col(RunIssue.run_id).in_(run_ids)).group_by(col(RunIssue.run_id))
        ).all():
            issue_counts[run_id] = count
        for region in session.exec(
            select(DocumentRegion).where(
                col(DocumentRegion.document_id).in_(document_ids), DocumentRegion.position_in_document == 1
            )
        ).all():
            first_pages[region.document_id] = region.page_id

    return [
        DocumentListItem(
            id=document.id,
            submission_id=document.submission_id,
            received_at=document.received_at,
            doc_type=run.doc_type,
            technical_status=run.technical_status,
            overall_status=run.overall_status,
            provider_rut=run.provider_rut,
            rut_is_substitute=run.rut_is_substitute,
            document_number=run.document_number,
            issue_date=run.issue_date,
            total_amount=run.total_amount,
            difference=run.difference,
            review_reason=run.review_reason,
            has_signature=run.has_signature,
            issue_count=issue_counts.get(run.id, 0),
            first_page_id=first_pages.get(document.id),
        )
        for document, run in rows
    ]


@router.get("/stats", response_model=DocumentStats)
def document_stats(session: SessionDep):
    """Cuántos documentos hay por estado y por tipo (según su resultado vigente)."""
    runs = aliased(ProcessingRun, _shown_runs())
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    total = 0
    for run in session.exec(select(runs)).all():
        total += 1
        by_status[_status(run)] = by_status.get(_status(run), 0) + 1
        if run.doc_type:
            by_type[run.doc_type] = by_type.get(run.doc_type, 0) + 1
    return DocumentStats(total=total, by_status=by_status, by_type=by_type)


def _get_or_404(session: Session, document_id: uuid.UUID) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return document


@router.post("/{document_id}/reprocess", response_model=RunSummary, status_code=status.HTTP_202_ACCEPTED)
def reprocess_document(document_id: uuid.UUID, session: SessionDep, background: BackgroundTasks):
    """Vuelve a extraer y validar un documento (por ejemplo, tras cambiar de modelo o de instrucciones).

    Crea un procesamiento nuevo; el resultado actual sigue vigente hasta que el nuevo termine bien.
    Si las imágenes, las instrucciones y el modelo no cambiaron, la IA responde desde la caché.
    """
    _get_or_404(session, document_id)
    runs = session.exec(select(ProcessingRun).where(ProcessingRun.document_id == document_id)).all()
    if not runs:
        raise HTTPException(status.HTTP_409_CONFLICT, "El documento aún no tiene procesamiento")
    latest = max(runs, key=lambda r: r.run_number)
    if latest.technical_status == "EN_PROCESO":
        raise HTTPException(status.HTTP_409_CONFLICT, "El documento ya se está procesando")
    if latest.doc_type == "DESCONOCIDO":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Un documento desconocido no se extrae; para reclasificarlo, vuelve a subir el archivo"
        )
    run = new_run_from(session, shown_run(runs))
    background.add_task(process_single_document, session.get_bind(), document_id)
    return RunSummary.model_validate(run)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: uuid.UUID, session: SessionDep):
    """Un documento con su procesamiento actual (o el más reciente si aún no hay): datos, estado de
    cada campo, alertas, bitácora de pasos y el historial de procesamientos."""
    document = _get_or_404(session, document_id)

    rows = session.exec(
        select(DocumentRegion, Page)
        .join(Page, col(Page.id) == DocumentRegion.page_id)
        .where(DocumentRegion.document_id == document_id)
        .order_by(col(DocumentRegion.position_in_document))
    ).all()
    regions = [
        RegionRead(
            id=region.id,
            page_id=page.id,
            file_id=page.file_id,
            page_number=page.page_number,
            index_on_page=region.index_on_page,
            bbox=region.bbox,
            position_hint=region.position_hint,
            has_crop=region.crop_key is not None,
        )
        for region, page in rows
    ]

    runs = session.exec(
        select(ProcessingRun).where(ProcessingRun.document_id == document_id).order_by(col(ProcessingRun.run_number))
    ).all()
    run = shown_run(runs)
    fields, issues, steps = [], [], []
    if run:
        order = {name: i for i, name in enumerate(FIELD_NAMES)}
        fields = sorted(
            session.exec(select(ExtractedField).where(ExtractedField.run_id == run.id)).all(),
            key=lambda f: order[f.field_name],
        )
        issues = session.exec(select(RunIssue).where(RunIssue.run_id == run.id)).all()
        steps = session.exec(
            select(RunStep).where(RunStep.run_id == run.id).order_by(col(RunStep.created_at))
        ).all()

    return DocumentDetail(
        id=document.id,
        submission_id=document.submission_id,
        received_at=document.received_at,
        regions=regions,
        run=RunRead.model_validate(run) if run else None,
        fields=[FieldRead.model_validate(f) for f in fields],
        issues=[IssueRead.model_validate(i) for i in issues],
        steps=[StepRead.model_validate(s) for s in steps],
        history=[RunSummary.model_validate(r) for r in runs],
    )
