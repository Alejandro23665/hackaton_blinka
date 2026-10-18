from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Column, DateTime, Text, func, text
from sqlmodel import Field, SQLModel


class Vendor(SQLModel, table=True):
    __tablename__ = "vendors"
    __table_args__ = (
        # Un monto acordado sin moneda (o al revés) no se puede comparar con nada
        CheckConstraint(
            "(agreed_amount IS NULL) = (agreed_currency IS NULL)", name="ck_vendors_agreement_complete"
        ),
        CheckConstraint("agreed_amount IS NULL OR agreed_amount > 0", name="ck_vendors_agreed_positive"),
        CheckConstraint(
            "agreement_tolerance_pct >= 0 AND agreement_tolerance_pct <= 100",
            name="ck_vendors_tolerance_range",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, unique=True)
    # Identificador fiscal (RUC/NIT/RFC…); permite reconocer al proveedor en facturas subidas
    tax_id: str | None = Field(default=None, max_length=50, unique=True)
    is_allowed: bool = Field(default=True)
    # Creado automáticamente desde una factura subida: falta que una persona lo apruebe
    needs_review: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})

    # Lo acordado con el proveedor: si una factura se desvía más que la tolerancia, se escala
    agreed_amount: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    agreed_currency: str | None = Field(default=None, max_length=3)
    agreement_tolerance_pct: Decimal = Field(
        default=Decimal(5), max_digits=5, decimal_places=2, sa_column_kwargs={"server_default": text("5")}
    )
    agreement_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
