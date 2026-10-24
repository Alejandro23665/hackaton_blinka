"""Segmentación y agrupación de punta a punta: lote → páginas → IA (simulada) → documentos."""
from app.ai.client import AIError
from tests.factories import detected, image_bytes, page_response, pdf_bytes

LEFT = {"x": 0, "y": 0, "w": 0.5, "h": 1}
RIGHT = {"x": 0.5, "y": 0, "w": 0.5, "h": 1}


def _lot(client, *files):
    created = client.post("/submissions", files=[("files", f) for f in files]).json()
    return client.get(f"/submissions/{created['id']}").json()


def test_mixed_pdf_becomes_separate_documents(client, fake_ai):
    fake_ai.pages = {
        1: page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "N° 000100")),
        2: page_response(detected("FACTURA_ELECTRONICA", None, "100", continuation=True)),
        3: page_response(
            detected("GUIA_DESPACHO", "GUÍA DE DESPACHO ELECTRÓNICA", "55", region=LEFT),
            detected("DESCONOCIDO", "BOLETA ELECTRÓNICA", None, index=2, region=RIGHT),
        ),
    }
    lot = _lot(client, ("lote.pdf", pdf_bytes(3), "application/pdf"))
    assert lot["status"] == "COMPLETADO"
    assert all(p["classification_status"] == "OK" for p in lot["files"][0]["pages"])

    invoice, guide, unknown = lot["documents"]
    assert invoice["doc_type"] == "FACTURA_ELECTRONICA"
    assert [p["page_number"] for p in invoice["pages"]] == [1, 2]
    assert (invoice["technical_status"], invoice["overall_status"]) == ("COMPLETADO", "PROCESADO")

    assert guide["doc_type"] == "GUIA_DESPACHO"
    assert (guide["pages"][0]["page_number"], guide["pages"][0]["bbox"]) == (3, LEFT)

    assert (unknown["doc_type"], unknown["overall_status"], unknown["technical_status"]) == (
        "DESCONOCIDO",
        "DESCONOCIDO",
        "COMPLETADO",
    )
    assert "BOLETA" in unknown["review_reason"]

    # La página 2 se analizó sabiendo cómo terminaba la 1 (para detectar la continuación)
    assert "FACTURA_ELECTRONICA N° 000100" in fake_ai.calls[1]["prompt"]
    assert "primera página" in fake_ai.calls[0]["prompt"]


def test_type_without_evidence_is_stored_as_unknown_with_warning(client, fake_ai):
    fake_ai.pages = {1: page_response(detected("FACTURA_ELECTRONICA", "BOLETA ELECTRÓNICA", "9"))}
    (document,) = _lot(client, ("foto.jpg", image_bytes(fmt="JPEG"), "image/jpeg"))["documents"]
    assert document["doc_type"] == "DESCONOCIDO" and document["overall_status"] == "DESCONOCIDO"
    assert document["issues"][0]["code"] == "CLASIFICACION_SIN_EVIDENCIA"


def test_quota_stops_the_lot_and_reprocessing_resumes_without_repeating_calls(client, fake_ai):
    fake_ai.pages = {
        1: page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", "1")),
        2: page_response(detected("CONTROL_INTERNO", None, "1", continuation=True)),
        3: page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", "2")),
    }
    fake_ai.errors = {2: AIError("Se agotó el límite diario", "CUOTA")}
    data = pdf_bytes(3)
    lot = _lot(client, ("controles.pdf", data, "application/pdf"), ("otra.png", image_bytes(), "image/png"))

    assert lot["status"] == "COMPLETADO_CON_ERRORES"
    statuses = [(p["classification_status"], p["classification_error"]) for p in lot["files"][0]["pages"]]
    assert statuses[0] == ("OK", None)
    assert statuses[1] == ("ERROR", "Se agotó el límite diario")
    assert statuses[2] == (None, None)
    assert lot["documents"] == []
    # Con la cuota agotada no se siguió con el segundo archivo
    assert [c["page"] for c in fake_ai.calls] == [1, 2]

    fake_ai.errors = {}
    fake_ai.calls.clear()
    client.post(f"/submissions/{lot['id']}/process")
    lot = client.get(f"/submissions/{lot['id']}").json()
    assert lot["status"] == "COMPLETADO"
    assert [c["page"] for c in fake_ai.calls] == [2, 3, 1]  # la página 1 no se vuelve a pedir
    assert [len(d["pages"]) for d in lot["documents"]] == [2, 1, 1]


def test_same_file_in_new_lot_reuses_documents_without_calling_ai(client, fake_ai):
    fake_ai.pages = {1: page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", "5"))}
    data = pdf_bytes(1)
    first = _lot(client, ("a.pdf", data, "application/pdf"))
    calls = len(fake_ai.calls)
    second = _lot(client, ("b.pdf", data, "application/pdf"))
    assert len(fake_ai.calls) == calls
    assert [d["id"] for d in second["documents"]] == [d["id"] for d in first["documents"]]
