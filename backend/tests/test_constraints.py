"""La base de datos hace cumplir las reglas críticas aunque el código se equivoque."""
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Document, ExtractedField, ProcessingRun, Submission


@pytest.fixture
def document(session):
    submission = Submission()
    session.add(submission)
    session.commit()
    document = Document(submission_id=submission.id)
    session.add(document)
    session.commit()
    return document


def _run(document, **values) -> ProcessingRun:
    defaults = {"document_id": document.id, "run_number": 1, "pipeline_version": "test"}
    return ProcessingRun(**{**defaults, **values})


def _completed(document, **values) -> ProcessingRun:
    defaults = {
        "technical_status": "COMPLETADO",
        "doc_type": "FACTURA_ELECTRONICA",
        "extraction_status": "COMPLETA",
        "validation_status": "CUADRA",
        "overall_status": "PROCESADO",
    }
    return _run(document, **{**defaults, **values})


def _rejected(session, obj) -> bool:
    session.add(obj)
    try:
        session.commit()
        return False
    except IntegrityError:
        session.rollback()
        return True


def test_valid_run_is_accepted(session, document):
    assert not _rejected(
        session,
        _completed(
            document,
            is_current=True,
            provider_rut="76123456-K",
            net_amount=Decimal(100000),
            vat_amount=Decimal(19000),
            total_amount=Decimal(119000),
            calculated_total=Decimal(119000),
            difference=Decimal(0),
        ),
    )


def test_substitute_rut_must_be_1_9(session, document):
    assert _rejected(session, _completed(document, provider_rut="76123456-K", rut_is_substitute=True))
    assert not _rejected(session, _completed(document, provider_rut="1-9", rut_is_substitute=True))


def test_unknown_document_cannot_have_accounting_data(session, document):
    assert _rejected(
        session,
        _completed(document, doc_type="DESCONOCIDO", overall_status="DESCONOCIDO", total_amount=Decimal(1000)),
    )


def test_mismatch_requires_data_and_a_difference_beyond_tolerance(session, document):
    # Sin datos no se puede afirmar un descuadre
    assert _rejected(session, _completed(document, validation_status="DESCUADRE", overall_status="DESCUADRE"))
    # Diferencia 0: no es descuadre
    assert _rejected(
        session,
        _completed(
            document,
            validation_status="DESCUADRE",
            overall_status="DESCUADRE",
            total_amount=Decimal(100),
            calculated_total=Decimal(100),
            difference=Decimal(0),
        ),
    )
    # La diferencia debe ser total declarado − calculado
    assert _rejected(
        session,
        _completed(document, total_amount=Decimal(120000), calculated_total=Decimal(119000), difference=Decimal(5)),
    )
    assert not _rejected(
        session,
        _completed(
            document,
            validation_status="DESCUADRE",
            overall_status="DESCUADRE",
            total_amount=Decimal(120000),
            calculated_total=Decimal(119000),
            difference=Decimal(1000),
        ),
    )


def test_only_one_current_run_and_only_if_completed(session, document):
    assert _rejected(session, _run(document, is_current=True))  # EN_PROCESO no puede ser el actual
    assert not _rejected(session, _completed(document, is_current=True))
    assert _rejected(session, _completed(document, run_number=2, is_current=True))
    assert not _rejected(session, _completed(document, run_number=2))


def test_completed_run_needs_overall_status_and_amounts_are_not_negative(session, document):
    assert _rejected(session, _run(document, technical_status="COMPLETADO"))
    assert _rejected(session, _completed(document, net_amount=Decimal(-1)))


def test_read_field_keeps_original_text(session, document):
    run = _completed(document)
    session.add(run)
    session.commit()
    assert _rejected(session, ExtractedField(run_id=run.id, field_name="ISSUE_DATE", status="LEIDO", is_required=True))
    assert not _rejected(
        session, ExtractedField(run_id=run.id, field_name="OTHER_TAXES_AMOUNT", status="AUSENTE", is_required=False)
    )
