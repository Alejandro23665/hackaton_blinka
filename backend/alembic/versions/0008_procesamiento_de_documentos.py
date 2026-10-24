"""Procesamiento de documentos: reemplaza el esquema de Rekreuz

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-24

Elimina las tablas de Rekreuz (facturas, proveedores, políticas, decisiones…) y crea las del
sistema de captura de documentos (docs/01-diseno.md). El código de Rekreuz se conserva en la
rama git rekreuz-final.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REKREUZ_TABLES = (
    "document_files", "documents", "decisions", "invoices", "vendors", "policies", "exchange_rates",
)
NEW_TABLES = (
    "run_steps", "run_issues", "extracted_fields", "processing_runs", "page_classifications",
    "document_regions", "documents", "submission_files", "pages", "submissions", "stored_files",
)


def upgrade() -> None:
    for table in REKREUZ_TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    op.create_table('stored_files',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.Text(), nullable=False),
    sa.Column('original_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=50), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('preprocess_status', sa.String(length=12), nullable=False),
    sa.Column('preprocess_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("preprocess_status IN ('PENDIENTE', 'LISTO', 'FALLIDO')", name='ck_stored_files_preprocess_status'),
    sa.CheckConstraint('page_count IS NULL OR page_count >= 1', name='ck_stored_files_page_count'),
    sa.CheckConstraint('size_bytes > 0', name='ck_stored_files_size'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('sha256'),
    sa.UniqueConstraint('storage_key')
    )
    op.create_table('submissions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('source', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.CheckConstraint("source IN ('UPLOAD', 'API')", name='ck_submissions_source'),
    sa.CheckConstraint("status IN ('RECIBIDO', 'EN_PROCESO', 'COMPLETADO', 'COMPLETADO_CON_ERRORES')", name='ck_submissions_status'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_submissions_status'), 'submissions', ['status'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('submission_id', sa.Uuid(), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_documents_submission_id'), 'documents', ['submission_id'], unique=False)
    op.create_table('pages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('file_id', sa.Uuid(), nullable=False),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('image_key', sa.Text(), nullable=False),
    sa.Column('width', sa.Integer(), nullable=False),
    sa.Column('height', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('page_number >= 1', name='ck_pages_page_number'),
    sa.ForeignKeyConstraint(['file_id'], ['stored_files.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('file_id', 'page_number', name='uq_pages_file_page')
    )
    op.create_index(op.f('ix_pages_file_id'), 'pages', ['file_id'], unique=False)
    op.create_table('submission_files',
    sa.Column('submission_id', sa.Uuid(), nullable=False),
    sa.Column('file_id', sa.Uuid(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['file_id'], ['stored_files.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['submission_id'], ['submissions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('submission_id', 'file_id'),
    sa.UniqueConstraint('submission_id', 'position', name='uq_submission_files_position')
    )
    op.create_table('document_regions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('page_id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('index_on_page', sa.Integer(), nullable=False),
    sa.Column('position_in_document', sa.Integer(), nullable=False),
    sa.Column('bbox', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('crop_key', sa.Text(), nullable=True),
    sa.Column('position_hint', sa.String(length=100), nullable=True),
    sa.CheckConstraint('index_on_page >= 1', name='ck_document_regions_index'),
    sa.CheckConstraint('position_in_document >= 1', name='ck_document_regions_position'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'position_in_document', name='uq_document_regions_position'),
    sa.UniqueConstraint('page_id', 'index_on_page', name='uq_document_regions_page_index')
    )
    op.create_index(op.f('ix_document_regions_document_id'), 'document_regions', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_regions_page_id'), 'document_regions', ['page_id'], unique=False)
    op.create_table('page_classifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('page_id', sa.Uuid(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('prompt_version', sa.String(length=20), nullable=False),
    sa.Column('response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('OK', 'ERROR')", name='ck_page_classifications_status'),
    sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_page_classifications_page_id'), 'page_classifications', ['page_id'], unique=False)
    op.create_index('uq_page_classifications_current', 'page_classifications', ['page_id'], unique=True, postgresql_where=sa.text('is_current'))
    op.create_table('processing_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('run_number', sa.Integer(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('technical_status', sa.String(length=20), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pipeline_version', sa.String(length=20), nullable=False),
    sa.Column('classifier_model', sa.String(length=100), nullable=True),
    sa.Column('extractor_model', sa.String(length=100), nullable=True),
    sa.Column('error_code', sa.String(length=40), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('doc_type', sa.String(length=20), nullable=True),
    sa.Column('classification_confidence', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('classification_evidence', sa.Text(), nullable=True),
    sa.Column('extraction_status', sa.String(length=20), nullable=True),
    sa.Column('validation_status', sa.String(length=20), nullable=True),
    sa.Column('overall_status', sa.String(length=20), nullable=True),
    sa.Column('review_reason', sa.Text(), nullable=True),
    sa.Column('provider_rut', sa.String(length=12), nullable=True),
    sa.Column('rut_is_substitute', sa.Boolean(), nullable=False),
    sa.Column('document_number', sa.String(length=40), nullable=True),
    sa.Column('issue_date', sa.Date(), nullable=True),
    sa.Column('net_amount', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('tax_amount', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('exempt_amount', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('total_amount', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('calculated_total', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('difference', sa.Numeric(precision=18, scale=2), nullable=True),
    sa.Column('total_tolerance', sa.Numeric(precision=18, scale=2), nullable=False),
    sa.Column('ocr_text', sa.Text(), nullable=True),
    sa.CheckConstraint("NOT is_current OR technical_status = 'COMPLETADO'", name='ck_processing_runs_current_completed'),
    sa.CheckConstraint("NOT rut_is_substitute OR provider_rut = '1-9'", name='ck_processing_runs_substitute_rut'),
    sa.CheckConstraint("doc_type <> 'DESCONOCIDO' OR (provider_rut IS NULL AND document_number IS NULL AND issue_date IS NULL AND net_amount IS NULL AND tax_amount IS NULL AND exempt_amount IS NULL AND total_amount IS NULL AND calculated_total IS NULL AND difference IS NULL)", name='ck_processing_runs_unknown_without_data'),
    sa.CheckConstraint("doc_type IS NULL OR doc_type IN ('GUIA_DESPACHO', 'CONTROL_INTERNO', 'FACTURA_ELECTRONICA', 'DESCONOCIDO')", name='ck_processing_runs_doc_type'),
    sa.CheckConstraint("extraction_status IS NULL OR extraction_status IN ('COMPLETA', 'INCOMPLETA', 'NO_APLICA')", name='ck_processing_runs_extraction'),
    sa.CheckConstraint("overall_status IS NULL OR overall_status IN ('PROCESADO', 'NO_LEGIBLE', 'DESCUADRE', 'DESCONOCIDO')", name='ck_processing_runs_overall'),
    sa.CheckConstraint("technical_status <> 'COMPLETADO' OR overall_status IS NOT NULL", name='ck_processing_runs_completed_status'),
    sa.CheckConstraint("technical_status IN ('EN_PROCESO', 'COMPLETADO', 'FALLIDO')", name='ck_processing_runs_technical'),
    sa.CheckConstraint("validation_status <> 'DESCUADRE' OR (difference IS NOT NULL AND abs(difference) > total_tolerance)", name='ck_processing_runs_mismatch'),
    sa.CheckConstraint("validation_status IS NULL OR validation_status IN ('CUADRA', 'DESCUADRE', 'INCOMPLETA', 'NO_APLICA')", name='ck_processing_runs_validation'),
    sa.CheckConstraint('classification_confidence IS NULL OR classification_confidence BETWEEN 0 AND 1', name='ck_processing_runs_confidence'),
    sa.CheckConstraint('difference IS NULL OR difference = total_amount - calculated_total', name='ck_processing_runs_difference'),
    sa.CheckConstraint('exempt_amount IS NULL OR exempt_amount >= 0', name='ck_processing_runs_exempt_amount'),
    sa.CheckConstraint('net_amount IS NULL OR net_amount >= 0', name='ck_processing_runs_net_amount'),
    sa.CheckConstraint('run_number >= 1', name='ck_processing_runs_number'),
    sa.CheckConstraint('tax_amount IS NULL OR tax_amount >= 0', name='ck_processing_runs_tax_amount'),
    sa.CheckConstraint('total_amount IS NULL OR total_amount >= 0', name='ck_processing_runs_total_amount'),
    sa.CheckConstraint('total_tolerance >= 0', name='ck_processing_runs_tolerance'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('document_id', 'run_number', name='uq_processing_runs_number')
    )
    op.create_index('ix_processing_runs_business_key', 'processing_runs', ['provider_rut', 'doc_type', 'document_number'], unique=False, postgresql_where=sa.text('is_current AND NOT rut_is_substitute'))
    op.create_index('ix_processing_runs_doc_type_current', 'processing_runs', ['doc_type'], unique=False, postgresql_where=sa.text('is_current'))
    op.create_index(op.f('ix_processing_runs_document_id'), 'processing_runs', ['document_id'], unique=False)
    op.create_index('ix_processing_runs_overall_current', 'processing_runs', ['overall_status'], unique=False, postgresql_where=sa.text('is_current'))
    op.create_index('uq_processing_runs_current', 'processing_runs', ['document_id'], unique=True, postgresql_where=sa.text('is_current'))
    op.create_table('extracted_fields',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('field_name', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('is_required', sa.Boolean(), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=True),
    sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
    sa.Column('region_id', sa.Uuid(), nullable=True),
    sa.Column('invalid_reason', sa.Text(), nullable=True),
    sa.CheckConstraint("field_name IN ('PROVIDER_RUT', 'DOCUMENT_NUMBER', 'ISSUE_DATE', 'NET_AMOUNT', 'TAX_AMOUNT', 'EXEMPT_AMOUNT', 'TOTAL_AMOUNT')", name='ck_extracted_fields_name'),
    sa.CheckConstraint("status <> 'LEIDO' OR raw_text IS NOT NULL", name='ck_extracted_fields_read_has_text'),
    sa.CheckConstraint("status IN ('LEIDO', 'AUSENTE', 'ILEGIBLE')", name='ck_extracted_fields_status'),
    sa.CheckConstraint('confidence IS NULL OR confidence BETWEEN 0 AND 1', name='ck_extracted_fields_confidence'),
    sa.ForeignKeyConstraint(['region_id'], ['document_regions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['run_id'], ['processing_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('run_id', 'field_name', name='uq_extracted_fields_run_field')
    )
    op.create_index(op.f('ix_extracted_fields_run_id'), 'extracted_fields', ['run_id'], unique=False)
    op.create_table('run_issues',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=40), nullable=False),
    sa.Column('severity', sa.String(length=12), nullable=False),
    sa.Column('field_name', sa.String(length=20), nullable=True),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.CheckConstraint("field_name IS NULL OR field_name IN ('PROVIDER_RUT', 'DOCUMENT_NUMBER', 'ISSUE_DATE', 'NET_AMOUNT', 'TAX_AMOUNT', 'EXEMPT_AMOUNT', 'TOTAL_AMOUNT')", name='ck_run_issues_field'),
    sa.CheckConstraint("severity IN ('ERROR', 'ADVERTENCIA', 'INFO')", name='ck_run_issues_severity'),
    sa.ForeignKeyConstraint(['run_id'], ['processing_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_run_issues_code'), 'run_issues', ['code'], unique=False)
    op.create_index(op.f('ix_run_issues_run_id'), 'run_issues', ['run_id'], unique=False)
    op.create_table('run_steps',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('step', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('cost_usd', sa.Numeric(precision=12, scale=6), nullable=True),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('OK', 'ERROR', 'OMITIDO')", name='ck_run_steps_status'),
    sa.CheckConstraint("step IN ('EXTRACCION', 'NORMALIZACION', 'VALIDACION')", name='ck_run_steps_step'),
    sa.CheckConstraint('attempts >= 0', name='ck_run_steps_attempts'),
    sa.ForeignKeyConstraint(['run_id'], ['processing_runs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_run_steps_run_id'), 'run_steps', ['run_id'], unique=False)


def downgrade() -> None:
    # Solo deshace este paso; el esquema de Rekreuz no se recrea (está en la rama rekreuz-final)
    for table in NEW_TABLES:
        op.drop_table(table)
