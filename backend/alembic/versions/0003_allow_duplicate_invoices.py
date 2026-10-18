"""Permitir facturas duplicadas: el agente las registra y las bloquea

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-17
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_invoices_vendor_number", "invoices", type_="unique")
    op.create_index("ix_invoices_vendor_number", "invoices", ["vendor_id", "invoice_number"])


def downgrade() -> None:
    # Falla si ya hay duplicados guardados: hay que resolverlos antes de volver atrás
    op.drop_index("ix_invoices_vendor_number", table_name="invoices")
    op.create_unique_constraint(
        "uq_invoices_vendor_number", "invoices", ["vendor_id", "invoice_number"]
    )
