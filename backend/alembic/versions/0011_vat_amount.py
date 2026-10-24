"""IVA por separado: processing_runs.vat_amount (tax_amount pasa a ser la suma de todos los impuestos)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATA_WITHOUT_VAT = (
    "provider_rut", "document_number", "issue_date", "net_amount", "tax_amount", "exempt_amount",
    "total_amount", "calculated_total", "difference",
)


def _unknown_without_data(columns: tuple[str, ...]) -> None:
    op.drop_constraint("ck_processing_runs_unknown_without_data", "processing_runs", type_="check")
    op.create_check_constraint(
        "ck_processing_runs_unknown_without_data",
        "processing_runs",
        "doc_type <> 'DESCONOCIDO' OR (" + " AND ".join(f"{c} IS NULL" for c in columns) + ")",
    )


def upgrade() -> None:
    op.add_column("processing_runs", sa.Column("vat_amount", sa.Numeric(18, 2), nullable=True))
    op.create_check_constraint(
        "ck_processing_runs_vat_amount", "processing_runs", "vat_amount IS NULL OR vat_amount >= 0"
    )
    columns = list(DATA_WITHOUT_VAT)
    columns.insert(columns.index("tax_amount") + 1, "vat_amount")
    _unknown_without_data(tuple(columns))


def downgrade() -> None:
    _unknown_without_data(DATA_WITHOUT_VAT)
    op.drop_constraint("ck_processing_runs_vat_amount", "processing_runs", type_="check")
    op.drop_column("processing_runs", "vat_amount")
