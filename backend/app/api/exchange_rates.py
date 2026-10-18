from fastapi import APIRouter, HTTPException, Path, status
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import ExchangeRate, Policy
from app.schemas import ExchangeRateRead, ExchangeRateUpsert
from app.services import fx

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])

CurrencyPath = Path(pattern=r"^[A-Za-z]{3}$", description="Código ISO 4217")


@router.get("", response_model=list[ExchangeRateRead])
def list_rates(session: SessionDep):
    return session.exec(select(ExchangeRate).order_by(col(ExchangeRate.currency))).all()


@router.put("/{currency}", response_model=ExchangeRateRead)
def upsert_rate(payload: ExchangeRateUpsert, session: SessionDep, currency: str = CurrencyPath):
    """Crea o actualiza cuántos USD vale 1 unidad de la moneda. USD es la referencia (siempre 1)."""
    currency = currency.upper()
    if currency == fx.PIVOT:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "USD es la moneda de referencia y siempre vale 1")
    rate = session.get(ExchangeRate, currency) or ExchangeRate(currency=currency, usd_per_unit=payload.usd_per_unit)
    rate.usd_per_unit = payload.usd_per_unit
    session.add(rate)
    session.commit()
    session.refresh(rate)
    return rate


@router.delete("/{currency}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rate(session: SessionDep, currency: str = CurrencyPath):
    currency = currency.upper()
    rate = session.get(ExchangeRate, currency)
    if rate is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tipo de cambio no encontrado")
    in_use = session.exec(select(Policy).where(Policy.base_currency == currency)).first()
    if in_use:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{currency} es la moneda base de la política '{in_use.name}'; cámbiala antes de borrar su tipo de cambio",
        )
    session.delete(rate)
    session.commit()
