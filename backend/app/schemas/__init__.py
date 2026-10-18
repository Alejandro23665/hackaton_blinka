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

class AgreementFields(BaseModel):
    """Lo acordado con el proveedor. Monto y moneda van juntos (o ninguno)."""

    agreed_amount: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)] | None = None
    agreed_currency: str | None = Field(default=None, min_length=3, max_length=3)
    agreement_tolerance_pct: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)] | None = None
    agreement_notes: str | None = Field(default=None, max_length=500)

    @field_validator("agreed_currency")
    @classmethod
    def upper_currency(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


def normalize_tax_id(value: str | None) -> str | None:
    """Solo letras y dígitos en mayúscula, igual que hace el agente al leer facturas."""
    cleaned = "".join(ch for ch in (value or "") if ch.isalnum()).upper()
    return cleaned or None


def check_agreement_complete(amount, currency) -> None:
    if (amount is None) != (currency is None):
        raise ValueError("El acuerdo necesita monto y moneda a la vez (o ninguno de los dos)")


class VendorCreate(AgreementFields):
    name: str = Field(min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=50)
    is_allowed: bool = True

    @field_validator("tax_id")
    @classmethod
    def clean_tax_id(cls, value: str | None) -> str | None:
        return normalize_tax_id(value)

    @model_validator(mode="after")
    def agreement_complete(self) -> "VendorCreate":
        check_agreement_complete(self.agreed_amount, self.agreed_currency)
        return self


class VendorUpdate(AgreementFields):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=50)
    is_allowed: bool | None = None

    @field_validator("tax_id")
    @classmethod
    def clean_tax_id(cls, value: str | None) -> str | None:
        return normalize_tax_id(value)


class VendorRead(ReadModel):
    id: int
    name: str
    tax_id: str | None
    is_allowed: bool
    needs_review: bool
    agreed_amount: Money | None
    agreed_currency: str | None
    agreement_tolerance_pct: Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
    agreement_notes: str | None
    created_at: datetime


# --- Policies --------------------------------------------------------------

class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    max_amount_per_invoice: PositiveMoney
    period_budget: PositiveMoney
    period: Literal["monthly", "weekly"] = "monthly"
    require_human_above: PositiveMoney
    allowed_currencies: list[str] = Field(min_length=1)
    # Moneda de los límites y del presupuesto; las facturas se convierten a ella
    base_currency: str = Field(default="USD", min_length=3, max_length=3)
    is_active: bool = True

    @field_validator("base_currency")
    @classmethod
    def upper_base(cls, value: str) -> str:
        return value.strip().upper()

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
    base_currency: str
    require_human_above: Money
    allowed_currencies: list[str]
    is_active: bool
    created_at: datetime


class BudgetStatus(BaseModel):
    policy_id: int
    period: str
    period_start: datetime
    base_currency: str
    period_budget: Money
    spent: Money
    remaining: Money
    # Monedas de facturas aprobadas que no se pudieron convertir (el gasto real puede ser mayor)
    missing_rates: list[str] = []


# --- Exchange rates --------------------------------------------------------

class ExchangeRateUpsert(BaseModel):
    usd_per_unit: Decimal = Field(gt=0, max_digits=18, decimal_places=8)


class ExchangeRateRead(ReadModel):
    currency: str
    usd_per_unit: Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
    updated_at: datetime


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
