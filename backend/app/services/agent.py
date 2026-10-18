"""Agente: reúne el contexto desde la BD, aplica el motor de reglas y registra la decisión."""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import Decision, Invoice, Policy, Vendor
from app.services import fx, rules

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
    session: Session,
    policy: Policy,
    now: datetime,
    exclude_invoice_id: int | None = None,
    rates: fx.Rates | None = None,
) -> tuple[Decimal, list[str]]:
    """Suma, en la moneda base de la política, de las facturas aprobadas/pagadas del periodo.

    Devuelve (total, monedas_sin_tipo_de_cambio). Las facturas en monedas que no se pueden
    convertir no se suman: se informan para que el presupuesto quede "no comprobable".
    """
    rates = rates if rates is not None else fx.load_rates(session)
    query = (
        select(Invoice.currency, func.sum(Invoice.amount))
        .where(
            col(Invoice.status).in_(SPENT_STATUSES),
            col(Invoice.created_at) >= period_start(policy.period, now),
        )
        .group_by(Invoice.currency)
    )
    if exclude_invoice_id is not None:
        query = query.where(Invoice.id != exclude_invoice_id)

    total, missing = Decimal(0), []
    for currency, amount in session.exec(query).all():
        conv = fx.convert(amount, currency, policy.base_currency, rates)
        if conv.ok:
            total += conv.converted
        else:
            missing.append(currency)
    return total, sorted(missing)


def evaluate_invoice(session: Session, invoice: Invoice) -> Decision:
    """Evalúa la factura con la política activa, guarda la decisión y actualiza su estado."""
    vendor = session.get(Vendor, invoice.vendor_id)
    policy = get_active_policy(session)
    rates = fx.load_rates(session)
    spent, spent_missing = (
        spent_in_period(session, policy, datetime.now(UTC), exclude_invoice_id=invoice.id, rates=rates)
        if policy is not None
        else (Decimal(0), [])
    )

    # Otra factura anterior con el mismo número y proveedor => esta es un duplicado
    duplicate_of = session.exec(
        select(Invoice)
        .where(
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.invoice_number == invoice.invoice_number,
            col(Invoice.id) < invoice.id,
        )
        .order_by(col(Invoice.id))
    ).first()

    # Facturas leídas de un archivo: la calidad de la extracción también cuenta
    raw = invoice.raw_data or {}
    extraction = raw.get("extraction") if raw.get("source") == "document" else None

    result = rules.evaluate(
        invoice,
        vendor,
        policy,
        spent,
        extraction=extraction,
        min_confidence=settings.EXTRACTION_MIN_CONFIDENCE,
        duplicate_of=duplicate_of,
        rates=rates,
        spent_missing=spent_missing,
    )

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


def review_invoice(
    session: Session, invoice: Invoice, outcome: str, explanation: str, reviewer: str
) -> Decision:
    """Decisión humana sobre una factura escalada. No vuelve a aplicar las reglas."""
    decision = Decision(
        invoice_id=invoice.id,
        policy_id=None,
        outcome=outcome,
        rules_evaluated=[],
        explanation=explanation,
        decided_by="human",
        reviewer=reviewer,
    )
    invoice.status = outcome
    session.add_all([decision, invoice])
    session.commit()
    session.refresh(decision)
    return decision
