from datetime import datetime

from sqlalchemy import Column, DateTime, func, text
from sqlmodel import Field, SQLModel


class Vendor(SQLModel, table=True):
    __tablename__ = "vendors"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, unique=True)
    # Identificador fiscal (RUC/NIT/RFC…); permite reconocer al proveedor en facturas subidas
    tax_id: str | None = Field(default=None, max_length=50, unique=True)
    is_allowed: bool = Field(default=True)
    # Creado automáticamente desde una factura subida: falta que una persona lo apruebe
    needs_review: bool = Field(default=False, sa_column_kwargs={"server_default": text("false")})
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
