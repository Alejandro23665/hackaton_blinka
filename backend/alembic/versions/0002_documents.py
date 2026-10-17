"""documents (facturas subidas) y proveedores pendientes de revisión

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("vendors", sa.Column("tax_id", sa.String(50), nullable=True))
    op.create_unique_constraint("vendors_tax_id_key", "vendors", ["tax_id"])
    op.add_column(
        "vendors",
        sa.Column("needs_review", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("stored_path", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("extraction", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("sha256"),
        sa.CheckConstraint(
            "status IN ('processing', 'processed', 'failed')", name="ck_documents_status"
        ),
    )
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_invoice_id", "documents", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_column("vendors", "needs_review")
    op.drop_constraint("vendors_tax_id_key", "vendors", type_="unique")
    op.drop_column("vendors", "tax_id")
