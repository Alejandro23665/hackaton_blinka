"""Archivos de facturas en Postgres (tabla document_files) en lugar de disco

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-18

Copia a la base los archivos que existan en backend/storage y elimina documents.stored_path.
Así el despliegue (Render, Railway…) no necesita disco persistente.
"""
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_STORAGE = Path(__file__).resolve().parents[2] / "storage"


def upgrade() -> None:
    op.create_table(
        "document_files",
        sa.Column(
            "document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("content", sa.LargeBinary(), nullable=False),
    )
    conn = op.get_bind()
    insert = sa.text("INSERT INTO document_files (document_id, content) VALUES (:id, :content)")
    for doc_id, stored_path in conn.execute(sa.text("SELECT id, stored_path FROM documents")):
        path = LEGACY_STORAGE / stored_path if stored_path else None
        if path and path.is_file():
            conn.execute(insert, {"id": doc_id, "content": path.read_bytes()})
    op.drop_column("documents", "stored_path")


def downgrade() -> None:
    # El contenido de los archivos se pierde al volver atrás (ya no se escribe en disco)
    op.add_column("documents", sa.Column("stored_path", sa.String(500), nullable=True))
    op.drop_table("document_files")
