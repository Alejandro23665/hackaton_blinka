"""IVA como campo propio y obligatorio; los demás impuestos (IABA, ILA…) en other_taxes_amount

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-25

processing_runs.tax_amount (suma de todos los impuestos) se reemplaza por other_taxes_amount (todos
menos el IVA); vat_amount ya existía. En extracted_fields y run_issues, TAX_AMOUNT pasa a VAT_AMOUNT
(en los datos existentes, el IVA era casi siempre el único impuesto). Conviene reprocesar los
documentos anteriores para obtener el desglose exacto.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_FIELDS = ("PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE", "NET_AMOUNT", "TAX_AMOUNT", "EXEMPT_AMOUNT", "TOTAL_AMOUNT")
NEW_FIELDS = (
    "PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE", "NET_AMOUNT", "VAT_AMOUNT", "OTHER_TAXES_AMOUNT",
    "EXEMPT_AMOUNT", "TOTAL_AMOUNT",
)
OLD_DATA = (
    "provider_rut", "document_number", "issue_date", "net_amount", "tax_amount", "vat_amount",
    "exempt_amount", "total_amount", "calculated_total", "difference",
)
NEW_DATA = (
    "provider_rut", "document_number", "issue_date", "net_amount", "vat_amount", "other_taxes_amount",
    "exempt_amount", "total_amount", "calculated_total", "difference",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def _field_checks(fields: tuple[str, ...]) -> None:
    op.drop_constraint("ck_extracted_fields_name", "extracted_fields", type_="check")
    op.create_check_constraint("ck_extracted_fields_name", "extracted_fields", _in("field_name", fields))
    op.drop_constraint("ck_run_issues_field", "run_issues", type_="check")
    op.create_check_constraint(
        "ck_run_issues_field", "run_issues", f"field_name IS NULL OR {_in('field_name', fields)}"
    )


def _unknown_without_data(columns: tuple[str, ...]) -> None:
    op.drop_constraint("ck_processing_runs_unknown_without_data", "processing_runs", type_="check")
    op.create_check_constraint(
        "ck_processing_runs_unknown_without_data",
        "processing_runs",
        "doc_type <> 'DESCONOCIDO' OR (" + " AND ".join(f"{c} IS NULL" for c in columns) + ")",
    )


def upgrade() -> None:
    op.add_column("processing_runs", sa.Column("other_taxes_amount", sa.Numeric(18, 2), nullable=True))
    # Desglose aproximado de los datos existentes: si no se sabía el IVA, el impuesto era el IVA
    op.execute("UPDATE processing_runs SET vat_amount = tax_amount WHERE vat_amount IS NULL AND tax_amount IS NOT NULL")
    op.execute(
        "UPDATE processing_runs SET other_taxes_amount = tax_amount - vat_amount "
        "WHERE tax_amount IS NOT NULL AND vat_amount IS NOT NULL AND tax_amount <> vat_amount"
    )
    _unknown_without_data(NEW_DATA)
    op.drop_constraint("ck_processing_runs_tax_amount", "processing_runs", type_="check")
    op.drop_column("processing_runs", "tax_amount")
    op.create_check_constraint(
        "ck_processing_runs_other_taxes_amount",
        "processing_runs",
        "other_taxes_amount IS NULL OR other_taxes_amount >= 0",
    )

    _field_checks(tuple(sorted(set(OLD_FIELDS) | set(NEW_FIELDS))))
    op.execute("UPDATE extracted_fields SET field_name = 'VAT_AMOUNT' WHERE field_name = 'TAX_AMOUNT'")
    op.execute("UPDATE run_issues SET field_name = 'VAT_AMOUNT' WHERE field_name = 'TAX_AMOUNT'")
    _field_checks(NEW_FIELDS)


def downgrade() -> None:
    op.add_column("processing_runs", sa.Column("tax_amount", sa.Numeric(18, 2), nullable=True))
    op.execute(
        "UPDATE processing_runs SET tax_amount = vat_amount + COALESCE(other_taxes_amount, 0) "
        "WHERE vat_amount IS NOT NULL"
    )
    op.drop_constraint("ck_processing_runs_other_taxes_amount", "processing_runs", type_="check")
    _unknown_without_data(OLD_DATA)
    op.drop_column("processing_runs", "other_taxes_amount")
    op.create_check_constraint(
        "ck_processing_runs_tax_amount", "processing_runs", "tax_amount IS NULL OR tax_amount >= 0"
    )
    _field_checks(tuple(sorted(set(OLD_FIELDS) | set(NEW_FIELDS))))
    op.execute("DELETE FROM extracted_fields WHERE field_name = 'OTHER_TAXES_AMOUNT'")
    op.execute("UPDATE extracted_fields SET field_name = 'TAX_AMOUNT' WHERE field_name = 'VAT_AMOUNT'")
    op.execute("UPDATE run_issues SET field_name = 'TAX_AMOUNT' WHERE field_name IN ('VAT_AMOUNT', 'OTHER_TAXES_AMOUNT')")
    _field_checks(OLD_FIELDS)
