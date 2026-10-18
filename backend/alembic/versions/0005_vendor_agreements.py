"""Acuerdo con cada proveedor (monto, moneda, tolerancia) para detectar facturas que no cuadran

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Todo opcional: los proveedores existentes quedan sin acuerdo (la regla no les aplica)
    op.add_column("vendors", sa.Column("agreed_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("vendors", sa.Column("agreed_currency", sa.String(3), nullable=True))
    op.add_column(
        "vendors",
        sa.Column("agreement_tolerance_pct", sa.Numeric(5, 2), server_default=sa.text("5"), nullable=False),
    )
    op.add_column("vendors", sa.Column("agreement_notes", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_vendors_agreement_complete", "vendors", "(agreed_amount IS NULL) = (agreed_currency IS NULL)"
    )
    op.create_check_constraint(
        "ck_vendors_agreed_positive", "vendors", "agreed_amount IS NULL OR agreed_amount > 0"
    )
    op.create_check_constraint(
        "ck_vendors_tolerance_range", "vendors", "agreement_tolerance_pct >= 0 AND agreement_tolerance_pct <= 100"
    )


def downgrade() -> None:
    op.drop_constraint("ck_vendors_tolerance_range", "vendors", type_="check")
    op.drop_constraint("ck_vendors_agreed_positive", "vendors", type_="check")
    op.drop_constraint("ck_vendors_agreement_complete", "vendors", type_="check")
    op.drop_column("vendors", "agreement_notes")
    op.drop_column("vendors", "agreement_tolerance_pct")
    op.drop_column("vendors", "agreed_currency")
    op.drop_column("vendors", "agreed_amount")
