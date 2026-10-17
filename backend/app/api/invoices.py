from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Decision, Invoice, Vendor
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
    return InvoiceDetail.model_validate(
        {
            **InvoiceRead.model_validate(invoice).model_dump(),
            "vendor": session.get(Vendor, invoice.vendor_id),
            "decisions": decisions,
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

    duplicate = session.exec(
        select(Invoice).where(
            Invoice.vendor_id == payload.vendor_id,
            Invoice.invoice_number == payload.invoice_number,
        )
    ).first()
    if duplicate:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"La factura {payload.invoice_number} de este proveedor ya existe (id {duplicate.id})",
        )

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
    agent.review_invoice(session, invoice, payload.outcome, payload.explanation)
    return _detail(session, invoice)
