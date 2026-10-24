import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.models import Document, DocumentRegion, ExtractedField, Page, ProcessingRun, RunIssue, RunStep
from app.models.enums import FIELD_NAMES
from app.pipeline.orchestrator import new_run_from, process_single_document
from app.schemas import (
    DocumentDetail,
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
