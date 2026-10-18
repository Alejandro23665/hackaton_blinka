"""Moneda base en políticas y tipos de cambio configurables

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Las políticas existentes quedan en USD: es como se interpretaban hasta ahora sus límites
    op.add_column(
        "policies", sa.Column("base_currency", sa.String(3), server_default="USD", nullable=False)
    )
    op.create_table(
        "exchange_rates",
        sa.Column("currency", sa.String(3), primary_key=True),
        sa.Column("usd_per_unit", sa.Numeric(18, 8), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("usd_per_unit > 0", name="ck_exchange_rates_positive"),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
    op.drop_column("policies", "base_currency")
