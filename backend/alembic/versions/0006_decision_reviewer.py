"""Nombre de quien revisa en las decisiones humanas

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Las decisiones humanas anteriores quedan sin nombre (no se inventa quién fue)
    op.add_column("decisions", sa.Column("reviewer", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("decisions", "reviewer")
