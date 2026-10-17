"""initial schema: policies, vendors, invoices, decisions

Revision ID: 0001
Revises:
Create Date: 2026-10-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(14, 2)


def created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("max_amount_per_invoice", MONEY, nullable=False),
        sa.Column("period_budget", MONEY, nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("require_human_above", MONEY, nullable=False),
        sa.Column("allowed_currencies", postgresql.JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        created_at(),
        sa.CheckConstraint("period IN ('monthly', 'weekly')", name="ck_policies_period"),
    )
    op.create_index(
        "uq_policies_single_active",
        "policies",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("is_allowed", sa.Boolean(), nullable=False),
        created_at(),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_number", sa.String(100), nullable=False),
        sa.Column("vendor_id", sa.Integer(), sa.ForeignKey("vendors.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False),
        created_at(),
        sa.UniqueConstraint("vendor_id", "invoice_number", name="uq_invoices_vendor_number"),
        sa.CheckConstraint("amount > 0", name="ck_invoices_amount_positive"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'blocked', 'escalated', 'paid')",
            name="ck_invoices_status",
        ),
    )
    op.create_index("ix_invoices_vendor_id", "invoices", ["vendor_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("policy_id", sa.Integer(), sa.ForeignKey("policies.id"), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("rules_evaluated", postgresql.JSONB(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("decided_by", sa.String(10), nullable=False),
        created_at(),
        sa.CheckConstraint(
            "outcome IN ('approved', 'blocked', 'escalated')", name="ck_decisions_outcome"
        ),
        sa.CheckConstraint("decided_by IN ('agent', 'human')", name="ck_decisions_decided_by"),
    )
    op.create_index("ix_decisions_invoice_created", "decisions", ["invoice_id", "created_at"])


def downgrade() -> None:
    op.drop_table("decisions")
    op.drop_table("invoices")
    op.drop_table("vendors")
    op.drop_table("policies")
