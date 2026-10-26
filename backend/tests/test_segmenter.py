"""Segmentador (comprobaciones del código) y agrupador. Sin base de datos ni red."""
import uuid

import pytest

from app.core.config import settings
from app.pipeline.grouper import group_pages
from app.pipeline.segmenter import PageAnalysis, Region, clean_region, normalize_number, verify_type
from tests.factories import detected, page_response

# --- Comprobación del tipo propuesto por la IA ---------------------------------------------


@pytest.mark.parametrize(
    ("doc_type", "evidence"),
    [
        ("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA"),
        ("FACTURA_ELECTRONICA", "Factura  Electronica"),
        ("GUIA_DESPACHO", "GUÍA DE DESPACHO ELECTRÓNICA"),
        ("GUIA_DESPACHO", "GUIA ELECTRÓNICA"),  # tickets de OXXO
        ("CONTROL_INTERNO", "CONTROL INTERNO"),
    ],
)
def test_type_with_printed_title_is_accepted(doc_type, evidence):
    assert verify_type(doc_type, evidence, 0.9) == (doc_type, [])


@pytest.mark.parametrize(
    ("doc_type", "evidence"),
    [
        ("FACTURA_ELECTRONICA", None),  # sin título visible
        ("FACTURA_ELECTRONICA", "BOLETA ELECTRÓNICA"),
        ("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA EXENTA"),
        ("FACTURA_ELECTRONICA", "LIQUIDACIÓN FACTURA ELECTRÓNICA"),
        ("GUIA_DESPACHO", "FACTURA ELECTRÓNICA"),
    ],
)
def test_type_without_matching_evidence_becomes_unknown(doc_type, evidence):
    final, issues = verify_type(doc_type, evidence, 0.99)
    assert final == "DESCONOCIDO" and issues[0]["code"] == "CLASIFICACION_SIN_EVIDENCIA"


def test_low_confidence_becomes_unknown():
    final, issues = verify_type("CONTROL_INTERNO", "CONTROL INTERNO", settings.CLASSIFICATION_MIN_CONFIDENCE - 0.01)
    assert final == "DESCONOCIDO" and issues[0]["code"] == "CLASIFICACION_DUDOSA"


def test_region_rules():
    full = Region(x=0, y=0, w=1, h=1)
    assert clean_region(Region(x=0.5, y=0, w=0.5, h=1), documents_on_page=1) == (None, [])
    assert clean_region(Region(x=0.5, y=0, w=0.5, h=1), 2)[0] == {"x": 0.5, "y": 0, "w": 0.5, "h": 1}
    bbox, issues = clean_region(Region(x=0.8, y=0, w=0.5, h=1), 2)  # se sale de la página
    assert bbox is None and issues[0]["code"] == "REGION_INVALIDA"
    assert clean_region(full, 2)[0] == {"x": 0, "y": 0, "w": 1, "h": 1}


def test_document_numbers_compare_by_digits():
    assert normalize_number("N° 001234") == normalize_number("1234") == "1234"
    assert normalize_number("sin número") is None


# --- Agrupador ------------------------------------------------------------------------------


def _pages(*responses):
    return [(uuid.uuid4(), PageAnalysis.model_validate(r)) for r in responses]


def test_multi_page_invoice_is_one_document():
    pages = _pages(
        page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRONICA", "100")),
        page_response(detected("FACTURA_ELECTRONICA", None, "100", continuation=True)),
        page_response(detected("DESCONOCIDO", None, None, continuation=True)),  # tercera hoja sin número
    )
    documents = group_pages(pages)
    assert len(documents) == 1
    assert [r.page_id for r in documents[0].regions] == [p for p, _ in pages]
    assert documents[0].doc_type == "FACTURA_ELECTRONICA"


def test_two_documents_on_one_page_keep_their_regions():
    left, right = {"x": 0, "y": 0, "w": 0.5, "h": 1}, {"x": 0.5, "y": 0, "w": 0.5, "h": 1}
    (page_id, analysis), = _pages(
        page_response(
            detected("FACTURA_ELECTRONICA", "FACTURA ELECTRONICA", "7", region=left),
            detected("GUIA_DESPACHO", "GUIA DE DESPACHO", "8", index=2, region=right),
        )
    )
    first, second = group_pages([(page_id, analysis)])
    assert (first.doc_type, first.regions[0].index_on_page, first.regions[0].bbox) == ("FACTURA_ELECTRONICA", 1, left)
    assert (second.doc_type, second.regions[0].index_on_page, second.regions[0].bbox) == ("GUIA_DESPACHO", 2, right)


def test_continuation_that_does_not_match_is_split_with_warning():
    documents = group_pages(
        _pages(
            page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRONICA", "100")),
            page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRONICA", "200", continuation=True)),
        )
    )
    assert len(documents) == 2
    assert documents[1].issues[0]["code"] == "AGRUPACION_DUDOSA"


def test_unknown_pages_are_never_merged():
    documents = group_pages(_pages(page_response(detected()), page_response(detected(continuation=True))))
    assert [d.doc_type for d in documents] == ["DESCONOCIDO", "DESCONOCIDO"]


def test_only_first_document_of_a_page_can_continue():
    documents = group_pages(
        _pages(
            page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", "1")),
            page_response(
                detected("CONTROL_INTERNO", "CONTROL INTERNO", "2", region={"x": 0, "y": 0, "w": 1, "h": 0.5}),
                detected("CONTROL_INTERNO", None, "1", continuation=True, index=2, region={"x": 0, "y": 0.5, "w": 1, "h": 0.5}),
            ),
        )
    )
    assert len(documents) == 3


def test_low_quality_page_adds_warning():
    (doc,) = group_pages(_pages(page_response(detected(), quality="BAJA", issues=["borrosa"])))
    assert doc.issues[0]["code"] == "BAJA_CALIDAD_IMAGEN" and "borrosa" in doc.issues[0]["message"]
