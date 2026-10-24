"""Segmentador (comprobaciones del código), agrupador y cliente de IA. Sin base de datos ni red."""
import uuid

import httpx
import pytest

from app.ai import client as ai
from app.core.config import settings
from app.pipeline.grouper import group_pages
from app.pipeline.segmenter import PageAnalysis, Region, clean_region, normalize_number, verify_type
from tests.factories import detected, page_response

# El cliente real, guardado antes de que el FakeAI de conftest lo sustituya en cada test
REAL_CALL_JSON = ai.call_json

# --- Comprobación del tipo propuesto por la IA ---------------------------------------------


@pytest.mark.parametrize(
    ("doc_type", "evidence"),
    [
        ("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA"),
        ("FACTURA_ELECTRONICA", "Factura  Electronica"),
        ("GUIA_DESPACHO", "GUÍA DE DESPACHO ELECTRÓNICA"),
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


# --- Cliente de IA (red simulada) -------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body
        self.headers = {"content-type": "application/json"}
        self.text = str(body)

    def json(self):
        return self._body


def _ok(content: str, cost=0.0):
    return FakeResponse(200, {"model": "m", "choices": [{"message": {"content": content}}], "usage": {"cost": cost}})


@pytest.fixture
def real_client(monkeypatch):
    """El cliente real (sin el FakeAI de conftest), con httpx.post simulado y sin esperas."""
    module = ai
    monkeypatch.setattr(module, "call_json", REAL_CALL_JSON)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    responses: list = []
    calls: list = []

    def post(url, json, headers, timeout):
        calls.append(json)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(module.httpx, "post", post)
    return module, responses, calls


def _call(module):
    return module.call_json(
        system="s", content=[module.text_part("t")], schema={}, schema_name="x", model="m", parse=lambda d: d["v"]
    )


def test_identical_call_uses_cache(real_client):
    module, responses, calls = real_client
    responses.append(_ok('{"v": 1}', cost=0.002))
    first = _call(module)
    second = _call(module)
    assert (first.parsed, first.cached, str(first.cost_usd)) == (1, False, "0.002")
    assert (second.parsed, second.cached) == (1, True)
    assert len(calls) == 1


def test_bad_format_is_retried_and_never_cached(real_client):
    module, responses, calls = real_client
    responses.extend([_ok("no es json"), _ok('{"otro": 1}'), _ok('```json\n{"v": 2}\n```')])
    assert _call(module).parsed == 2 and len(calls) == 3


def test_daily_quota_is_not_retried(real_client):
    module, responses, calls = real_client
    responses.append(FakeResponse(429, {"error": {"message": "Rate limit exceeded: free-models-per-day"}}))
    with pytest.raises(module.AIError) as exc:
        _call(module)
    assert exc.value.code == "CUOTA" and len(calls) == 1


def test_transient_errors_are_retried(real_client):
    module, responses, calls = real_client
    responses.extend([FakeResponse(503, {"error": {"message": "ocupado"}}), httpx.ConnectError("x"), _ok('{"v": 3}')])
    result = _call(module)
    assert result.parsed == 3 and result.attempts == 3


def test_missing_key(real_client, monkeypatch):
    module, _, _ = real_client
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", None)
    with pytest.raises(module.AIError) as exc:
        _call(module)
    assert exc.value.code == "SIN_CLAVE"


def test_rejected_key_is_not_retried(real_client):
    module, responses, calls = real_client
    responses.append(FakeResponse(401, {"error": {"message": "User not found."}}))
    with pytest.raises(module.AIError) as exc:
        _call(module)
    assert exc.value.code == "CLAVE" and "OPENROUTER_API_KEY" in str(exc.value) and len(calls) == 1
