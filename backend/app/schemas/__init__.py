"""DTOs de entrada/salida de la API (separados de las tablas)."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator, model_validator

# Los montos viajan como número en JSON (más cómodo para el frontend)
Money = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
PositiveMoney = Annotated[Money, Field(gt=0, max_digits=14, decimal_places=2)]


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Vendors ---------------------------------------------------------------

class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=50)
    is_allowed: bool = True


class VendorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=50)
    is_allowed: bool | None = None


class VendorRead(ReadModel):
    id: int
    name: str
    tax_id: str | None
    is_allowed: bool
    needs_review: bool
    created_at: datetime


# --- Policies --------------------------------------------------------------

class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    max_amount_per_invoice: PositiveMoney
    period_budget: PositiveMoney
    period: Literal["monthly", "weekly"] = "monthly"
    require_human_above: PositiveMoney
    allowed_currencies: list[str] = Field(min_length=1)
    is_active: bool = True

    @field_validator("allowed_currencies")
    @classmethod
    def normalize_currencies(cls, value: list[str]) -> list[str]:
        normalized = [c.strip().upper() for c in value]
        if any(len(c) != 3 for c in normalized):
            raise ValueError("Cada moneda debe ser un código ISO de 3 letras")
        return sorted(set(normalized))

    @model_validator(mode="after")
    def check_thresholds(self) -> "PolicyCreate":
        if self.require_human_above > self.max_amount_per_invoice:
            raise ValueError(
                "require_human_above debe ser <= max_amount_per_invoice; si no, nunca se escalaría"
            )
        return self


class PolicyRead(ReadModel):
    id: int
    name: str
    max_amount_per_invoice: Money
    period_budget: Money
    period: str
    require_human_above: Money
    allowed_currencies: list[str]
    is_active: bool
    created_at: datetime


class BudgetStatus(BaseModel):
    policy_id: int
    period: str
    period_start: datetime
    period_budget: Money
    spent: Money
    remaining: Money


# --- Invoices --------------------------------------------------------------

class InvoiceCreate(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=100)
    vendor_id: int
    amount: PositiveMoney
    currency: str = Field(min_length=3, max_length=3)
    due_date: date
    raw_data: dict[str, Any] | None = None

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        return value.upper()


class InvoiceRead(ReadModel):
    id: int
    invoice_number: str
    vendor_id: int
    amount: Money
    currency: str
    due_date: date
    status: str
    raw_data: dict[str, Any]
    created_at: datetime


# --- Decisions -------------------------------------------------------------

class DecisionRead(ReadModel):
    id: int
    invoice_id: int
    policy_id: int | None
    outcome: str
    rules_evaluated: list[dict[str, Any]]
    explanation: str
    decided_by: str
    created_at: datetime


# --- Documents -------------------------------------------------------------

class DocumentRead(ReadModel):
    id: int
    original_name: str
    content_type: str
    size_bytes: int
    status: str
    extraction: dict[str, Any] | None
    error: str | None
    invoice_id: int | None
    created_at: datetime


class InvoiceDetail(InvoiceRead):
    vendor: VendorRead
    decisions: list[DecisionRead]
    document: DocumentRead | None = None


class ReviewRequest(BaseModel):
    outcome: Literal["approved", "blocked"]
    explanation: str = Field(min_length=1)
