from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

INVOICE_STATUSES = ("pending", "approved", "blocked", "escalated", "paid")


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"
    __table_args__ = (
        # Evita pagar dos veces la misma factura del mismo proveedor
        UniqueConstraint("vendor_id", "invoice_number", name="uq_invoices_vendor_number"),
        CheckConstraint("amount > 0", name="ck_invoices_amount_positive"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'blocked', 'escalated', 'paid')",
            name="ck_invoices_status",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    invoice_number: str = Field(max_length=100)
    vendor_id: int = Field(foreign_key="vendors.id", index=True)
    amount: Decimal = Field(max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    due_date: date
    status: str = Field(default="pending", max_length=20, index=True)
    raw_data: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSONB, nullable=False)
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
