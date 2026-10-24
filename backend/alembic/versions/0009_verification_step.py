"""Paso VERIFICACION: segunda lectura independiente de cada documento

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-24
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _steps_check(steps: tuple[str, ...]) -> None:
    op.drop_constraint("ck_run_steps_step", "run_steps", type_="check")
    allowed = ", ".join(f"'{s}'" for s in steps)
    op.create_check_constraint("ck_run_steps_step", "run_steps", f"step IN ({allowed})")


def upgrade() -> None:
    _steps_check(("EXTRACCION", "VERIFICACION", "NORMALIZACION", "VALIDACION"))


def downgrade() -> None:
    op.execute("DELETE FROM run_steps WHERE step = 'VERIFICACION'")
    _steps_check(("EXTRACCION", "NORMALIZACION", "VALIDACION"))
