from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, DateTime, func
from sqlmodel import Field, SQLModel


class ExchangeRate(SQLModel, table=True):
    """Tipo de cambio que define la empresa: cuántos USD vale 1 unidad de la moneda.

    USD actúa como moneda pivote (vale 1 y no necesita fila), así cualquier par se convierte
    con una sola fila por moneda: monto * usd_per_unit(origen) / usd_per_unit(destino).
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (CheckConstraint("usd_per_unit > 0", name="ck_exchange_rates_positive"),)

    currency: str = Field(primary_key=True, min_length=3, max_length=3)
    usd_per_unit: Decimal = Field(max_digits=18, decimal_places=8)
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        ),
    )
