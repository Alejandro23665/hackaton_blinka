"""Resultado de procesar un documento: datos, estados, detalle por campo, alertas y bitácora.

Cada procesamiento es una fila nueva en processing_runs; solo una por documento es la actual.
Las restricciones CHECK hacen cumplir en la propia base las reglas críticas de la especificación.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Numeric, Text, UniqueConstraint, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import timestamp, uuid_pk
from app.models.enums import (
    DOC_TYPES,
    EXTRACTION_STATUSES,
    FIELD_NAMES,
    FIELD_STATUSES,
    ISSUE_SEVERITIES,
    OVERALL_STATUSES,
    RUN_STEPS,
    STEP_STATUSES,
    SUBSTITUTE_RUT,
    TECHNICAL_STATUSES,
    VALIDATION_STATUSES,
    one_of,
)

AMOUNT_COLUMNS = ("net_amount", "vat_amount", "other_taxes_amount", "exempt_amount", "total_amount")
DATA_COLUMNS = ("provider_rut", "document_number", "issue_date", *AMOUNT_COLUMNS, "calculated_total", "difference")


def _money():
    """Monto exacto (numeric). NULL = sin valor: nunca 0 por defecto."""
    return Field(default=None, sa_column=Column(Numeric(18, 2), nullable=True))


def _nullable_one_of(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IS NULL OR {one_of(column, values)}"


class ProcessingRun(SQLModel, table=True):
    __tablename__ = "processing_runs"
    __table_args__ = (
        UniqueConstraint("document_id", "run_number", name="uq_processing_runs_number"),
        # Un único resultado actual por documento
        Index("uq_processing_runs_current", "document_id", unique=True, postgresql_where=text("is_current")),
        Index("ix_processing_runs_overall_current", "overall_status", postgresql_where=text("is_current")),
        Index("ix_processing_runs_doc_type_current", "doc_type", postgresql_where=text("is_current")),
        # Detectar el mismo documento fotografiado dos veces (no se usa con el RUT de sustitución)
        Index(
            "ix_processing_runs_business_key",
            "provider_rut",
            "doc_type",
            "document_number",
            postgresql_where=text("is_current AND NOT rut_is_substitute"),
        ),
        CheckConstraint("run_number >= 1", name="ck_processing_runs_number"),
        CheckConstraint(one_of("technical_status", TECHNICAL_STATUSES), name="ck_processing_runs_technical"),
        CheckConstraint(_nullable_one_of("doc_type", DOC_TYPES), name="ck_processing_runs_doc_type"),
        CheckConstraint(_nullable_one_of("extraction_status", EXTRACTION_STATUSES), name="ck_processing_runs_extraction"),
        CheckConstraint(_nullable_one_of("validation_status", VALIDATION_STATUSES), name="ck_processing_runs_validation"),
        CheckConstraint(_nullable_one_of("overall_status", OVERALL_STATUSES), name="ck_processing_runs_overall"),
        CheckConstraint(
            "classification_confidence IS NULL OR classification_confidence BETWEEN 0 AND 1",
            name="ck_processing_runs_confidence",
        ),
        # Solo un procesamiento terminado puede ser el actual, y todo procesamiento terminado tiene estado
        CheckConstraint("NOT is_current OR technical_status = 'COMPLETADO'", name="ck_processing_runs_current_completed"),
        CheckConstraint(
            "technical_status <> 'COMPLETADO' OR overall_status IS NOT NULL", name="ck_processing_runs_completed_status"
        ),
        # 1-9 nunca se confunde con un RUT real
        CheckConstraint(
            f"NOT rut_is_substitute OR provider_rut = '{SUBSTITUTE_RUT}'", name="ck_processing_runs_substitute_rut"
        ),
        # Un documento desconocido no tiene datos contables
        CheckConstraint(
            "doc_type <> 'DESCONOCIDO' OR (" + " AND ".join(f"{c} IS NULL" for c in DATA_COLUMNS) + ")",
            name="ck_processing_runs_unknown_without_data",
        ),
        # No hay DESCUADRE sin los datos para comprobarlo ni con una diferencia dentro de la tolerancia
        CheckConstraint(
            "validation_status <> 'DESCUADRE' OR (difference IS NOT NULL AND abs(difference) > total_tolerance)",
            name="ck_processing_runs_mismatch",
        ),
        CheckConstraint(
            "difference IS NULL OR difference = total_amount - calculated_total", name="ck_processing_runs_difference"
        ),
        CheckConstraint("total_tolerance >= 0", name="ck_processing_runs_tolerance"),
        CheckConstraint(
            "signature_confidence IS NULL OR signature_confidence BETWEEN 0 AND 1",
            name="ck_processing_runs_signature_confidence",
        ),
        *(CheckConstraint(f"{c} IS NULL OR {c} >= 0", name=f"ck_processing_runs_{c}") for c in AMOUNT_COLUMNS),
    )

    id: uuid.UUID = uuid_pk()
    document_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    run_number: int
    is_current: bool = False

    # Técnico
    technical_status: str = Field(default="EN_PROCESO", max_length=20)
    started_at: datetime = timestamp()
    # Fecha de procesamiento
    finished_at: datetime | None = timestamp(default_now=False)
    pipeline_version: str = Field(max_length=20)
    classifier_model: str | None = Field(default=None, max_length=100)
    extractor_model: str | None = Field(default=None, max_length=100)
    error_code: str | None = Field(default=None, max_length=40)
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # Clasificación
    doc_type: str | None = Field(default=None, max_length=20)
    classification_confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(4, 3), nullable=True))
    classification_evidence: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # Estados (dimensiones independientes + estado general derivado por código)
    extraction_status: str | None = Field(default=None, max_length=20)
    validation_status: str | None = Field(default=None, max_length=20)
    overall_status: str | None = Field(default=None, max_length=20)
    review_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # Datos normalizados
    provider_rut: str | None = Field(default=None, max_length=12)
    rut_is_substitute: bool = False
    # Texto: conserva los ceros iniciales
    document_number: str | None = Field(default=None, max_length=40)
    issue_date: date | None = None
    net_amount: Decimal | None = _money()
    # IVA (obligatorio)
    vat_amount: Decimal | None = _money()
    # Suma de los demás impuestos (IABA, ILA…), opcionales
    other_taxes_amount: Decimal | None = _money()
    exempt_amount: Decimal | None = _money()
    total_amount: Decimal | None = _money()

    # Validación
    calculated_total: Decimal | None = _money()
    difference: Decimal | None = _money()
    # Tolerancia con la que se juzgó este documento
    total_tolerance: Decimal = Field(default=Decimal(0), sa_column=Column(Numeric(18, 2), nullable=False))

    # Firma manuscrita de recepción. NULL = no se analizó (desconocidos o aún sin extracción)
    has_signature: bool | None = None
    signature_confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(4, 3), nullable=True))

    # Auditoría: transcripción completa del documento
    ocr_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class ExtractedField(SQLModel, table=True):
    """Cómo se obtuvo cada campo: leído, ausente o ilegible, con el texto original y la confianza."""

    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint("run_id", "field_name", name="uq_extracted_fields_run_field"),
        CheckConstraint(one_of("field_name", FIELD_NAMES), name="ck_extracted_fields_name"),
        CheckConstraint(one_of("status", FIELD_STATUSES), name="ck_extracted_fields_status"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 0 AND 1", name="ck_extracted_fields_confidence"),
        # Un campo leído siempre conserva lo que se vio en el documento
        CheckConstraint("status <> 'LEIDO' OR raw_text IS NOT NULL", name="ck_extracted_fields_read_has_text"),
    )

    id: uuid.UUID = uuid_pk()
    run_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    field_name: str = Field(max_length=20)
    status: str = Field(max_length=10)
    # Si era obligatorio para ese tipo de documento en ese momento
    is_required: bool
    raw_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    confidence: Decimal | None = Field(default=None, sa_column=Column(Numeric(4, 3), nullable=True))
    region_id: uuid.UUID | None = Field(
        default=None, sa_column=Column(Uuid, ForeignKey("document_regions.id", ondelete="SET NULL"), nullable=True)
    )
    invalid_reason: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class RunIssue(SQLModel, table=True):
    """Alertas de un procesamiento, incluidas las secundarias: ninguna se pierde por el estado principal."""

    __tablename__ = "run_issues"
    __table_args__ = (
        CheckConstraint(one_of("severity", ISSUE_SEVERITIES), name="ck_run_issues_severity"),
        CheckConstraint(_nullable_one_of("field_name", FIELD_NAMES), name="ck_run_issues_field"),
    )

    id: uuid.UUID = uuid_pk()
    run_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    code: str = Field(max_length=40, index=True)
    severity: str = Field(max_length=12)
    field_name: str | None = Field(default=None, max_length=20)
    message: str = Field(sa_column=Column(Text, nullable=False))
    details: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))


class RunStep(SQLModel, table=True):
    """Bitácora: qué paso se ejecutó, con qué modelo, cuánto tardó y qué respondió la IA."""

    __tablename__ = "run_steps"
    __table_args__ = (
        CheckConstraint(one_of("step", RUN_STEPS), name="ck_run_steps_step"),
        CheckConstraint(one_of("status", STEP_STATUSES), name="ck_run_steps_status"),
        CheckConstraint("attempts >= 0", name="ck_run_steps_attempts"),
    )

    id: uuid.UUID = uuid_pk()
    run_id: uuid.UUID = Field(
        sa_column=Column(Uuid, ForeignKey("processing_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    )
    step: str = Field(max_length=20)
    status: str = Field(max_length=10)
    attempts: int = 1
    model: str | None = Field(default=None, max_length=100)
    duration_ms: int | None = None
    cost_usd: Decimal | None = Field(default=None, sa_column=Column(Numeric(12, 6), nullable=True))
    output: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
    error_message: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = timestamp()
