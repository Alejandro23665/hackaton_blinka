import uuid

from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Document, DocumentRegion, ExtractedField, Page, ProcessingRun, RunIssue, RunStep
from app.models.enums import FIELD_NAMES
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


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(document_id: uuid.UUID, session: SessionDep):
    """Un documento con su procesamiento más reciente: datos, estado de cada campo, alertas,
    bitácora de pasos y el historial de procesamientos anteriores."""
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")

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
    run = runs[-1] if runs else None
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
