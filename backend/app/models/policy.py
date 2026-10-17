from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, DateTime, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Policy(SQLModel, table=True):
    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint("period IN ('monthly', 'weekly')", name="ck_policies_period"),
        # Solo una política activa a la vez
        Index(
            "uq_policies_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    max_amount_per_invoice: Decimal = Field(max_digits=14, decimal_places=2)
    period_budget: Decimal = Field(max_digits=14, decimal_places=2)
    period: str = Field(default="monthly", max_length=20)
    require_human_above: Decimal = Field(max_digits=14, decimal_places=2)
    allowed_currencies: list[str] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    is_active: bool = Field(default=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
