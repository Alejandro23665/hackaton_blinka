from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import update
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Policy
from app.schemas import BudgetStatus, PolicyCreate, PolicyRead
from app.services import agent

router = APIRouter(prefix="/policies", tags=["policies"])


def _deactivate_all(session: SessionDep) -> None:
    # Se ejecuta antes de insertar/activar otra para respetar el índice de política única
    session.exec(update(Policy).where(col(Policy.is_active)).values(is_active=False))
    session.flush()


def _get_active_or_404(session: SessionDep) -> Policy:
    policy = agent.get_active_policy(session)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No hay política activa")
    return policy


@router.get("", response_model=list[PolicyRead])
def list_policies(session: SessionDep):
    return session.exec(select(Policy).order_by(col(Policy.created_at).desc())).all()


@router.post("", response_model=PolicyRead, status_code=status.HTTP_201_CREATED)
def create_policy(payload: PolicyCreate, session: SessionDep):
    """Crea una política. Si es activa, desactiva la anterior (las políticas no se editan)."""
    if payload.is_active:
        _deactivate_all(session)
    policy = Policy(**payload.model_dump())
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy


@router.get("/active", response_model=PolicyRead)
def get_active_policy(session: SessionDep):
    return _get_active_or_404(session)


@router.get("/active/budget", response_model=BudgetStatus)
def get_active_budget(session: SessionDep):
    policy = _get_active_or_404(session)
    now = datetime.now(UTC)
    spent = agent.spent_in_period(session, policy, now)
    return BudgetStatus(
        policy_id=policy.id,
        period=policy.period,
        period_start=agent.period_start(policy.period, now),
        period_budget=policy.period_budget,
        spent=spent,
        remaining=policy.period_budget - spent,
    )


@router.post("/{policy_id}/activate", response_model=PolicyRead)
def activate_policy(policy_id: int, session: SessionDep):
    policy = session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Política no encontrada")
    _deactivate_all(session)
    policy.is_active = True
    session.add(policy)
    session.commit()
    session.refresh(policy)
    return policy
