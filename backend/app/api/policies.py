from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import update
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Decision, Policy
from app.schemas import BudgetStatus, PolicyCreate, PolicyRead
from app.services import agent, fx

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
    if fx.rate_between(payload.base_currency, fx.PIVOT, fx.load_rates(session)) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Configura primero el tipo de cambio de {payload.base_currency} para usarla como moneda base",
        )
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
    spent, missing = agent.spent_in_period(session, policy, now)
    return BudgetStatus(
        policy_id=policy.id,
        period=policy.period,
        period_start=agent.period_start(policy.period, now),
        base_currency=policy.base_currency,
        period_budget=policy.period_budget,
        spent=spent,
        remaining=policy.period_budget - spent,
        missing_rates=missing,
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


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_policy(policy_id: int, session: SessionDep):
    """Elimina una política. Las decisiones tomadas con ella conservan sus reglas y su explicación,
    pero dejan de apuntar a la política. Si era la activa, el agente escalará todo hasta activar otra."""
    policy = session.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Política no encontrada")
    session.exec(update(Decision).where(Decision.policy_id == policy_id).values(policy_id=None))
    session.delete(policy)
    session.commit()
