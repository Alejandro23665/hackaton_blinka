import csv
import io
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlmodel import Session, col, select

from app.api.deps import SessionDep
from app.models import Decision, Invoice, Policy, Vendor
from app.schemas import DecisionLogRow, DecisionRead

router = APIRouter(prefix="/decisions", tags=["decisions"])

OUTCOME_LABELS = {"approved": "Aprobada", "escalated": "Escalada", "blocked": "Bloqueada"}
RULE_LABELS = {
    "vendor_allowed": "Proveedor autorizado",
    "duplicate_invoice": "Control de duplicados",
    "agreement_match": "Acuerdo con el proveedor",
    "active_policy": "Política activa",
    "document_extraction": "Lectura del documento",
    "invoice_totals": "Suma de la factura",
    "currency_allowed": "Moneda permitida",
    "currency_conversion": "Conversión a moneda base",
    "max_amount_per_invoice": "Máximo por factura",
    "period_budget": "Presupuesto del periodo",
    "require_human_above": "Umbral de revisión humana",
}


@router.get("", response_model=list[DecisionRead])
def list_decisions(
    session: SessionDep,
    outcome: str | None = None,
    decided_by: str | None = None,
    limit: int = 100,
):
    query = (
        select(Decision)
        .order_by(col(Decision.created_at).desc(), col(Decision.id).desc())
        .limit(min(limit, 500))
    )
    if outcome:
        query = query.where(Decision.outcome == outcome)
    if decided_by:
        query = query.where(Decision.decided_by == decided_by)
    return session.exec(query).all()


def _log_rows(
    session: Session,
    outcome: str | None,
    decided_by: str | None,
    q: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int | None,
) -> list[DecisionLogRow]:
    query = (
        select(Decision, Invoice, Vendor, Policy)
        .join(Invoice, Invoice.id == Decision.invoice_id)
        .join(Vendor, Vendor.id == Invoice.vendor_id)
        .join(Policy, Policy.id == Decision.policy_id, isouter=True)
        .order_by(col(Decision.created_at).desc(), col(Decision.id).desc())
    )
    if outcome:
        query = query.where(Decision.outcome == outcome)
    if decided_by:
        query = query.where(Decision.decided_by == decided_by)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                col(Invoice.invoice_number).ilike(pattern),
                col(Vendor.name).ilike(pattern),
                col(Decision.reviewer).ilike(pattern),
            )
        )
    if date_from:
        query = query.where(col(Decision.created_at) >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.where(col(Decision.created_at) < datetime.combine(date_to + timedelta(days=1), time.min))
    if limit:
        query = query.limit(limit)

    return [
        DecisionLogRow(
            id=d.id,
            created_at=d.created_at,
            invoice_id=i.id,
            invoice_number=i.invoice_number,
            vendor_name=v.name,
            amount=i.amount,
            currency=i.currency,
            outcome=d.outcome,
            decided_by=d.decided_by,
            reviewer=d.reviewer,
            policy_name=p.name if p else None,
            failed_rules=[r["rule"] for r in d.rules_evaluated if not r.get("passed")],
            explanation=d.explanation,
        )
        for d, i, v, p in session.exec(query).all()
    ]


@router.get("/log", response_model=list[DecisionLogRow])
def decision_log(
    session: SessionDep,
    outcome: str | None = None,
    decided_by: str | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=200, le=1000),
):
    """Registro de decisiones con los datos de cada factura: qué se pagó, frenó o escaló y por qué."""
    return _log_rows(session, outcome, decided_by, q, date_from, date_to, limit)


@router.get("/export.csv")
def export_decisions(
    session: SessionDep,
    outcome: str | None = None,
    decided_by: str | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    """El registro completo en CSV (sustituye la hoja de cálculo de conciliación).

    Separador ';' y BOM UTF-8 para que Excel en español lo abra con columnas y tildes correctas.
    """
    rows = _log_rows(session, outcome, decided_by, q, date_from, date_to, limit=None)
    buffer = io.StringIO()
    buffer.write("\ufeff")
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "Fecha", "Factura", "Proveedor", "Monto", "Moneda", "Resultado", "Decidido por", "Revisor",
        "Política", "Reglas incumplidas", "Explicación",
    ])
    for r in rows:
        writer.writerow([
            r.created_at.strftime("%Y-%m-%d %H:%M"),
            r.invoice_number,
            r.vendor_name,
            f"{r.amount:.2f}".replace(".", ","),
            r.currency,
            OUTCOME_LABELS.get(r.outcome, r.outcome),
            "Agente" if r.decided_by == "agent" else "Humano",
            r.reviewer or "",
            r.policy_name or "",
            ", ".join(RULE_LABELS.get(rule, rule) for rule in r.failed_rules),
            r.explanation,
        ])
    filename = f"blinka-registro-{date.today():%Y%m%d}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{decision_id}", response_model=DecisionRead)
def get_decision(decision_id: int, session: SessionDep):
    decision = session.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decisión no encontrada")
    return decision
