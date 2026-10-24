"""Firma manuscrita: processing_runs.has_signature y signature_confidence

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("processing_runs", sa.Column("has_signature", sa.Boolean(), nullable=True))
    op.add_column("processing_runs", sa.Column("signature_confidence", sa.Numeric(4, 3), nullable=True))
    op.create_check_constraint(
        "ck_processing_runs_signature_confidence",
        "processing_runs",
        "signature_confidence IS NULL OR signature_confidence BETWEEN 0 AND 1",
    )


def downgrade() -> None:
    op.drop_constraint("ck_processing_runs_signature_confidence", "processing_runs", type_="check")
    op.drop_column("processing_runs", "signature_confidence")
    op.drop_column("processing_runs", "has_signature")
