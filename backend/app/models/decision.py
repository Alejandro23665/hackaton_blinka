from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

DECISION_OUTCOMES = ("approved", "blocked", "escalated")
DECIDED_BY = ("agent", "human")


class Decision(SQLModel, table=True):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('approved', 'blocked', 'escalated')", name="ck_decisions_outcome"
        ),
        CheckConstraint("decided_by IN ('agent', 'human')", name="ck_decisions_decided_by"),
        # Para obtener rápido la última decisión de una factura
        Index("ix_decisions_invoice_created", "invoice_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id")
    # Nullable: una decisión humana puede no depender de una política
    policy_id: int | None = Field(default=None, foreign_key="policies.id")
    outcome: str = Field(max_length=20)
    rules_evaluated: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSONB, nullable=False)
    )
    explanation: str = Field(sa_column=Column(Text, nullable=False))
    decided_by: str = Field(default="agent", max_length=10)
    # Nombre de la persona que tomó la decisión (solo decisiones humanas): trazabilidad
    reviewer: str | None = Field(default=None, max_length=100)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
