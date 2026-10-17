"""Agente: reúne el contexto desde la BD, aplica el motor de reglas y registra la decisión."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import Decision, Invoice, Policy, Vendor
from app.services import rules

# Estados que cuentan como dinero comprometido en el presupuesto
SPENT_STATUSES = ("approved", "paid")
# Estados que el agente puede volver a evaluar (approved/paid ya son finales)
REEVALUABLE_STATUSES = ("pending", "escalated", "blocked")


def get_active_policy(session: Session) -> Policy | None:
    return session.exec(select(Policy).where(col(Policy.is_active))).first()


def period_start(period: str, now: datetime) -> datetime:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        return day_start - timedelta(days=day_start.weekday())  # lunes
    return day_start.replace(day=1)


def spent_in_period(
    session: Session, policy: Policy, now: datetime, exclude_invoice_id: int | None = None
) -> Decimal:
    """Suma de facturas aprobadas/pagadas desde el inicio del periodo.

    MVP: se asume una sola moneda base para el presupuesto.
    """
    query = select(func.coalesce(func.sum(Invoice.amount), 0)).where(
        col(Invoice.status).in_(SPENT_STATUSES),
        col(Invoice.created_at) >= period_start(policy.period, now),
    )
    if exclude_invoice_id is not None:
        query = query.where(Invoice.id != exclude_invoice_id)
    return Decimal(session.exec(query).one())


def evaluate_invoice(session: Session, invoice: Invoice) -> Decision:
    """Evalúa la factura con la política activa, guarda la decisión y actualiza su estado."""
    vendor = session.get(Vendor, invoice.vendor_id)
    policy = get_active_policy(session)
    spent = (
        spent_in_period(session, policy, datetime.now(UTC), exclude_invoice_id=invoice.id)
        if policy is not None
        else Decimal(0)
    )

    result = rules.evaluate(invoice, vendor, policy, spent)

    decision = Decision(
        invoice_id=invoice.id,
        policy_id=policy.id if policy else None,
        outcome=result.outcome,
        rules_evaluated=[r.to_dict() for r in result.rules],
        explanation=result.explanation,
        decided_by="agent",
    )
    invoice.status = result.outcome
    session.add_all([decision, invoice])
    session.commit()
    session.refresh(decision)
    return decision


def review_invoice(session: Session, invoice: Invoice, outcome: str, explanation: str) -> Decision:
    """Decisión humana sobre una factura escalada. No vuelve a aplicar las reglas."""
    decision = Decision(
        invoice_id=invoice.id,
        policy_id=None,
        outcome=outcome,
        rules_evaluated=[],
        explanation=explanation,
        decided_by="human",
    )
    invoice.status = outcome
    session.add_all([decision, invoice])
    session.commit()
    session.refresh(decision)
    return decision
