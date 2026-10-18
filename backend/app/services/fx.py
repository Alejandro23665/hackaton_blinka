"""Conversión de monedas con los tipos de cambio que configura la empresa.

USD es la moneda pivote: cada tipo de cambio dice cuántos USD vale 1 unidad de la moneda.
Si falta un tipo de cambio se devuelve None (nunca 0): sin conversión no se puede saber si una
factura cumple los límites, y el agente debe escalarla en vez de aprobarla.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, select

from app.models import ExchangeRate

PIVOT = "USD"
CENT = Decimal("0.01")

Rates = dict[str, Decimal]


@dataclass(frozen=True)
class Conversion:
    amount: Decimal  # monto original
    currency: str  # moneda original
    base_currency: str
    rate: Decimal | None  # 1 unidad original = rate unidades base
    converted: Decimal | None  # monto en moneda base (None si falta el tipo de cambio)

    @property
    def ok(self) -> bool:
        return self.converted is not None

    @property
    def same_currency(self) -> bool:
        return self.currency == self.base_currency


def load_rates(session: Session) -> Rates:
    rates = {r.currency.upper(): Decimal(r.usd_per_unit) for r in session.exec(select(ExchangeRate)).all()}
    rates[PIVOT] = Decimal(1)
    return rates


def rate_between(source: str, target: str, rates: Rates) -> Decimal | None:
    source, target = source.upper(), target.upper()
    if source == target:
        return Decimal(1)
    if source not in rates or target not in rates:
        return None
    return rates[source] / rates[target]


def convert(amount: Decimal, source: str, target: str, rates: Rates) -> Conversion:
    rate = rate_between(source, target, rates)
    converted = None if rate is None else (Decimal(amount) * rate).quantize(CENT, rounding=ROUND_HALF_UP)
    return Conversion(Decimal(amount), source.upper(), target.upper(), rate, converted)


def missing_rates(currencies: list[str], base_currency: str, rates: Rates) -> list[str]:
    """Monedas que no se pueden convertir a la moneda base."""
    return sorted({c.upper() for c in currencies if rate_between(c, base_currency, rates) is None})
