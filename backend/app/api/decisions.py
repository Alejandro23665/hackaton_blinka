from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Decision
from app.schemas import DecisionRead

router = APIRouter(prefix="/decisions", tags=["decisions"])


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


@router.get("/{decision_id}", response_model=DecisionRead)
def get_decision(decision_id: int, session: SessionDep):
    decision = session.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Decisión no encontrada")
    return decision
