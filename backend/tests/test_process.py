"""Procesamiento de punta a punta: subida → IA (simulada) → documentos_procesados."""
from app.ai.client import AIError
from tests.factories import (
    ABSENT,
    detected,
    extraction,
    image_bytes,
    page_response,
    pdf_bytes,
    reading,
    tax_line,
)

INVOICE = page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "000123"))
CONTROL = page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", "2388"))
LEFT = {"x": 0, "y": 0, "w": 0.5, "h": 1}
RIGHT = {"x": 0.5, "y": 0, "w": 0.5, "h": 1}


def _upload(client, *files):
    """Sube y devuelve el trabajo terminado (en los tests, el segundo plano corre antes de responder)."""
    response = client.post("/trabajos", files=[("files", f) for f in files])
    assert response.status_code == 202, response.text
    return client.get(f"/trabajos/{response.json()['id']}").json()


def _image(n=1):
    return (f"{n}.png", image_bytes(10 + n, 10), "image/png")


def _documents(client, **params):
    return client.get("/documentos", params=params).json()["documentos"]


def test_correct_invoice_is_stored_as_legible(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(signed=True)]
    job = _upload(client, _image())
    assert job["estado"] == "TERMINADO"
    (result,) = job["archivos"][0]["documentos"]
    assert (result["tipo"], result["resultado"], result["observaciones"]) == ("FC", "GUARDADO", "LEGIBLE")

    doc = client.get(f"/documentos/{result['id']}").json()
    assert {k: doc[k] for k in ("tipo", "rut_proveedor", "folio", "fecha", "firma", "observaciones", "requiere_revision")} == {
        "tipo": "FC", "rut_proveedor": "76123456-0", "folio": "000123", "fecha": "2026-10-14",
        "firma": True, "observaciones": "LEGIBLE", "requiere_revision": False,
    }
    assert (doc["total_neto"], doc["iva"], doc["impuestos"], doc["total"]) == (100000, 19000, None, 119000)
    # El revisor puede ver el archivo original
    image = client.get(f"/documentos/{doc['id']}/imagen")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"


def test_mismatch_goes_to_human_review(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(TOTAL_AMOUNT=reading("$ 120.000"))]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["observaciones"], doc["requiere_revision"], doc["total"]) == ("DESCUADRE", True, 120000)


def test_illegible_required_amount_stores_zeros_and_goes_to_review(client, fake_ai):
    fake_ai.pages = {1: CONTROL}
    fake_ai.extractions = [extraction(NET_AMOUNT=reading("2.5??", status="ILEGIBLE", confidence=0.2))]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["observaciones"], doc["requiere_revision"]) == ("NO_LEGIBLE", True)
    assert (doc["total_neto"], doc["iva"], doc["impuestos"], doc["total"]) == (0, 0, 0, 0)


def test_other_taxes_and_exempt_are_stored_together_as_impuestos(client, fake_ai):
    fake_ai.pages = {1: CONTROL}
    fake_ai.extractions = [
        extraction(
            NET_AMOUNT=reading("$ 2.579"),
            EXEMPT_AMOUNT=reading("$ 100"),
            TOTAL_AMOUNT=reading("$ 3.266"),
            tax_lines=[tax_line("98", label="ILL(10,0%)"), tax_line("489")],
        )
    ]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["total_neto"], doc["iva"], doc["impuestos"], doc["total"], doc["observaciones"]) == (
        2579, 489, 198, 3266, "LEGIBLE"
    )


def test_unknown_documents_are_discarded(client, fake_ai):
    fake_ai.pages = {
        1: page_response(
            detected("CONTROL_INTERNO", "CONTROL INTERNO", "2388", region=LEFT),
            detected("DESCONOCIDO", "BOLETA ELECTRÓNICA", None, index=2, region=RIGHT),
        )
    }
    job = _upload(client, _image())
    results = job["archivos"][0]["documentos"]
    assert [(r["tipo"], r["resultado"]) for r in results] == [("CI", "GUARDADO"), ("DESCONOCIDO", "DESCARTADO")]
    assert "BOLETA" in results[1]["mensaje"]
    assert len(_documents(client)) == 1
    assert len(fake_ai.extraction_calls) == 1  # al desconocido no se le extraen datos


def test_multipage_pdf_with_several_documents(client, fake_ai):
    fake_ai.pages = {
        1: page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "N° 000100")),
        2: page_response(detected("FACTURA_ELECTRONICA", None, "100", continuation=True)),
        3: page_response(detected("GUIA_DESPACHO", "GUÍA DE DESPACHO ELECTRÓNICA", "55")),
    }
    fake_ai.extractions = [extraction(), extraction(DOCUMENT_NUMBER=reading("N° 55"))]
    job = _upload(client, ("lote.pdf", pdf_bytes(3), "application/pdf"))
    assert [(r["tipo"], r["folio"]) for r in job["archivos"][0]["documentos"]] == [("FC", "000123"), ("GD", "55")]
    # La factura de 2 hojas se leyó como un solo documento, con sus 2 imágenes
    assert [call["images"] for call in fake_ai.extraction_calls] == [2, 1]


def test_same_document_uploaded_twice_is_not_duplicated(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    _upload(client, _image(1))
    job = _upload(client, _image(2))  # otra foto del mismo documento
    (result,) = job["archivos"][0]["documentos"]
    assert result["resultado"] == "DUPLICADO" and "000123" in result["mensaje"]
    assert len(_documents(client)) == 1


def test_illegible_rut_is_stored_as_substitute_and_not_treated_as_duplicate(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    unreadable = reading("76.1??.456-0", status="ILEGIBLE", confidence=0.3)
    fake_ai.extractions = [extraction(PROVIDER_RUT=unreadable), extraction(PROVIDER_RUT=unreadable)]
    _upload(client, _image(1))
    _upload(client, _image(2))
    docs = _documents(client)
    assert [(d["rut_proveedor"], d["observaciones"]) for d in docs] == [("1-9", "NO_LEGIBLE")] * 2


def test_signature_counts_only_if_both_readings_see_it(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(signed=True)]
    fake_ai.verifications = [extraction(signed=False)]
    _upload(client, _image())
    assert _documents(client)[0]["firma"] is False


def test_second_reading_disagreement_makes_the_document_not_legible(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(ISSUE_DATE=reading("10.10.2025", confidence=0.9))]
    fake_ai.verifications = [extraction(ISSUE_DATE=reading("18-10-2026", confidence=0.8))]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["fecha"], doc["observaciones"]) == (None, "NO_LEGIBLE")


def test_unvalued_dispatch_guide_is_legible_without_amounts(client, fake_ai):
    fake_ai.pages = {1: page_response(detected("GUIA_DESPACHO", "GUÍA DE DESPACHO ELECTRÓNICA", "55"))}
    fake_ai.extractions = [extraction(NET_AMOUNT=ABSENT, VAT_AMOUNT=ABSENT, TOTAL_AMOUNT=ABSENT)]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["observaciones"], doc["total_neto"], doc["iva"], doc["impuestos"], doc["total"]) == (
        "LEGIBLE", None, None, None, None
    )


def test_quota_stops_the_job_and_keeps_what_was_saved(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(), AIError("Se agotó el límite diario", "CUOTA")]
    job = _upload(client, _image(1), _image(2), _image(3))
    assert job["estado"] == "DETENIDO"
    assert [f["estado"] for f in job["archivos"]] == ["TERMINADO", "ERROR", "OMITIDO"]
    assert len(_documents(client)) == 1


def test_provider_error_on_one_document_does_not_stop_the_rest(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [AIError("OpenRouter respondió 502", "PROVEEDOR"), extraction(DOCUMENT_NUMBER=reading("N° 7"))]
    job = _upload(client, _image(1), _image(2))
    assert job["estado"] == "TERMINADO"
    assert [d["resultado"] for f in job["archivos"] for d in f["documentos"]] == ["ERROR", "GUARDADO"]


def test_invalid_uploads_are_rejected(client):
    assert client.post("/trabajos", files=[("files", ("a.txt", b"hola", "text/plain"))]).status_code == 415
    assert client.post("/trabajos", files=[("files", ("a.png", b"", "image/png"))]).status_code == 422


def test_filters_and_summary(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [
        extraction(),
        extraction(DOCUMENT_NUMBER=reading("N° 2"), TOTAL_AMOUNT=reading("$ 1")),
        extraction(DOCUMENT_NUMBER=reading("N° 3"), ISSUE_DATE=reading("?", status="ILEGIBLE")),
    ]
    _upload(client, _image(1), _image(2), _image(3))
    assert {d["folio"] for d in _documents(client, requiere_revision=True)} == {"2", "3"}
    assert [d["folio"] for d in _documents(client, observaciones="DESCUADRE")] == ["2"]
    assert [d["folio"] for d in _documents(client, q="0001")] == ["000123"]
    assert _documents(client, tipo="CI") == []
    summary = client.get("/documentos/resumen").json()
    assert summary == {
        "total": 3,
        "requieren_revision": 2,
        "por_observaciones": {"LEGIBLE": 1, "DESCUADRE": 1, "NO_LEGIBLE": 1},
        "por_tipo": {"FC": 3},
    }
    assert [t["documento"] for t in client.get("/tipos-documentos").json()] == ["FC", "CI", "GD"]
    assert client.get("/documentos/999").status_code == 404
