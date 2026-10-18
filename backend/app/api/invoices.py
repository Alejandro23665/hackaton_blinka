from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Decision, Document, Invoice, Vendor
from app.schemas import InvoiceCreate, InvoiceDetail, InvoiceRead, ReviewRequest
from app.services import agent

router = APIRouter(prefix="/invoices", tags=["invoices"])


def _get_or_404(session: SessionDep, invoice_id: int) -> Invoice:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Factura no encontrada")
    return invoice


def _detail(session: SessionDep, invoice: Invoice) -> InvoiceDetail:
    decisions = session.exec(
        select(Decision)
        .where(Decision.invoice_id == invoice.id)
        .order_by(col(Decision.created_at), col(Decision.id))
    ).all()
    document = session.exec(select(Document).where(Document.invoice_id == invoice.id)).first()
    return InvoiceDetail.model_validate(
        {
            **InvoiceRead.model_validate(invoice).model_dump(),
            "vendor": session.get(Vendor, invoice.vendor_id),
            "decisions": decisions,
            "document": document,
        }
    )


@router.get("", response_model=list[InvoiceRead])
def list_invoices(session: SessionDep, status: str | None = None, vendor_id: int | None = None):
    query = select(Invoice).order_by(col(Invoice.created_at).desc(), col(Invoice.id).desc())
    if status:
        query = query.where(Invoice.status == status)
    if vendor_id:
        query = query.where(Invoice.vendor_id == vendor_id)
    return session.exec(query).all()


@router.post("", response_model=InvoiceDetail, status_code=status.HTTP_201_CREATED)
def create_invoice(payload: InvoiceCreate, session: SessionDep):
    """Ingresa una factura y el agente la evalúa de inmediato."""
    if session.get(Vendor, payload.vendor_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El proveedor no existe")

    # Un duplicado (mismo proveedor y número) se registra y el agente lo bloquea explicando el motivo
    data = payload.model_dump(exclude={"raw_data"})
    raw_data = payload.raw_data or payload.model_dump(mode="json", exclude={"raw_data"})
    invoice = Invoice(**data, raw_data=raw_data, status="pending")
    session.add(invoice)
    session.commit()
    session.refresh(invoice)

    agent.evaluate_invoice(session, invoice)
    return _detail(session, invoice)


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: int, session: SessionDep):
    return _detail(session, _get_or_404(session, invoice_id))


@router.post("/{invoice_id}/evaluate", response_model=InvoiceDetail)
def reevaluate_invoice(invoice_id: int, session: SessionDep):
    """Vuelve a evaluar con la política activa (útil tras cambiar políticas o proveedores)."""
    invoice = _get_or_404(session, invoice_id)
    if invoice.status not in agent.REEVALUABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Una factura en estado '{invoice.status}' no se reevalúa"
        )
    agent.evaluate_invoice(session, invoice)
    return _detail(session, invoice)


@router.post("/{invoice_id}/review", response_model=InvoiceDetail)
def review_invoice(invoice_id: int, payload: ReviewRequest, session: SessionDep):
    """Decisión humana sobre una factura escalada."""
    invoice = _get_or_404(session, invoice_id)
    if invoice.status != "escalated":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Solo se pueden revisar facturas en estado 'escalated'"
        )
    agent.review_invoice(session, invoice, payload.outcome, payload.explanation, payload.reviewer)
    return _detail(session, invoice)


# Dinero ya comprometido: estas facturas forman parte del registro de pagos y no se borran
UNDELETABLE_STATUSES = ("approved", "paid")


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_invoice(invoice_id: int, session: SessionDep):
    """Elimina una factura bloqueada, escalada o pendiente, con sus decisiones y su archivo."""
    invoice = _get_or_404(session, invoice_id)
    if invoice.status in UNDELETABLE_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Una factura aprobada no se puede eliminar: es un pago comprometido y su decisión debe "
            "poder explicarse después.",
        )
    for decision in session.exec(select(Decision).where(Decision.invoice_id == invoice_id)).all():
        session.delete(decision)
    # El contenido del archivo (document_files) se borra con el documento: ON DELETE CASCADE
    for document in session.exec(select(Document).where(Document.invoice_id == invoice_id)).all():
        session.delete(document)
    session.delete(invoice)
    session.commit()
