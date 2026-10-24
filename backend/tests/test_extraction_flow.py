"""Extracción y normalización de punta a punta: lote → documentos → extractor (simulado) → datos."""
from app.ai.client import AIError
from tests.factories import ABSENT, detected, extraction, image_bytes, page_response, pdf_bytes, reading

LEFT = {"x": 0, "y": 0, "w": 0.5, "h": 1}
RIGHT = {"x": 0.5, "y": 0, "w": 0.5, "h": 1}
INVOICE = page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "000123"))


def _lot(client, *files):
    created = client.post("/submissions", files=[("files", f) for f in files]).json()
    return client.get(f"/submissions/{created['id']}").json()


def _document(client, lot, index=0):
    return client.get(f"/documents/{lot['documents'][index]['id']}").json()


def test_invoice_fields_are_extracted_and_normalized(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    lot = _lot(client, ("factura.png", image_bytes(), "image/png"))
    assert lot["status"] == "COMPLETADO"
    summary = lot["documents"][0]
    assert (summary["provider_rut"], summary["document_number"], summary["issue_date"]) == (
        "76123456-0",
        "000123",
        "2026-10-14",
    )

    detail = _document(client, lot)
    run = detail["run"]
    assert (float(run["net_amount"]), float(run["vat_amount"]), float(run["total_amount"])) == (100000, 19000, 119000)
    assert run["exempt_amount"] is None  # ausente, no 0
    assert run["rut_is_substitute"] is False
    assert (run["technical_status"], run["overall_status"]) == ("COMPLETADO", "PROCESADO")
    assert run["extractor_model"] == "fake/extractor" and run["ocr_text"].startswith("FACTURA")

    fields = {f["field_name"]: f for f in detail["fields"]}
    assert fields["NET_AMOUNT"]["raw_text"] == "$ 100.000" and fields["NET_AMOUNT"]["status"] == "LEIDO"
    assert fields["EXEMPT_AMOUNT"]["status"] == "AUSENTE" and fields["EXEMPT_AMOUNT"]["is_required"] is False
    assert fields["TOTAL_AMOUNT"]["is_required"] is True
    assert fields["PROVIDER_RUT"]["region_id"] == detail["regions"][0]["id"]
    assert [s["step"] for s in detail["steps"]] == ["EXTRACCION", "VERIFICACION", "NORMALIZACION", "VALIDACION"]
    assert detail["issues"] == []


def test_partially_illegible_document_keeps_what_was_read(client, fake_ai):
    # Caso 3 de la especificación: número y montos legibles; fecha y RUT no
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [
        extraction(
            PROVIDER_RUT=reading("76.1??.456-0", status="ILEGIBLE", confidence=0.3),
            ISSUE_DATE=reading("0?/10/2026", status="ILEGIBLE", confidence=0.4),
        )
    ]
    detail = _document(client, _lot(client, ("borrosa.jpg", image_bytes(fmt="JPEG"), "image/jpeg")))
    run = detail["run"]
    assert (run["provider_rut"], run["rut_is_substitute"], run["issue_date"]) == ("1-9", True, None)
    assert run["document_number"] == "000123" and float(run["total_amount"]) == 119000
    fields = {f["field_name"]: f for f in detail["fields"]}
    assert fields["PROVIDER_RUT"]["raw_text"] == "76.1??.456-0"  # el texto visto queda para auditoría
    assert sorted(i["code"] for i in detail["issues"]) == ["CAMPO_ILEGIBLE", "RUT_SUSTITUTO"]


def test_documents_sharing_a_page_are_read_from_their_crops(client, fake_ai):
    fake_ai.pages = {
        1: page_response(
            detected("GUIA_DESPACHO", "GUÍA DE DESPACHO ELECTRÓNICA", "8841", region=LEFT),
            detected("DESCONOCIDO", "BOLETA ELECTRÓNICA", None, index=2, region=RIGHT),
        )
    }
    lot = _lot(client, ("doble.jpg", image_bytes(800, 400, fmt="JPEG"), "image/jpeg"))
    assert len(fake_ai.extraction_calls) == 1  # la boleta (desconocida) no se extrae
    assert "GUÍA DE DESPACHO" in fake_ai.extraction_calls[0]["prompt"]

    guide = _document(client, lot, 0)
    region = guide["regions"][0]
    assert region["has_crop"] is True
    crop = client.get(f"/regions/{region['id']}/crop")
    assert crop.status_code == 200 and crop.headers["content-type"] == "image/jpeg"

    unknown = _document(client, lot, 1)
    assert unknown["regions"][0]["has_crop"] is False and unknown["fields"] == []


def test_multi_page_document_sends_all_its_pages(client, fake_ai):
    fake_ai.pages = {
        1: page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", "552")),
        2: page_response(detected("CONTROL_INTERNO", None, "552", continuation=True)),
    }
    _lot(client, ("control.pdf", pdf_bytes(2), "application/pdf"))
    assert fake_ai.extraction_calls[0]["images"] == 2


def test_unvalued_dispatch_guide_does_not_require_amounts(client, fake_ai):
    fake_ai.pages = {1: page_response(detected("GUIA_DESPACHO", "GUÍA DE DESPACHO", "77"))}
    fake_ai.extractions = [
        extraction(NET_AMOUNT=ABSENT, VAT_AMOUNT=ABSENT, EXEMPT_AMOUNT=ABSENT, TOTAL_AMOUNT=ABSENT)
    ]
    detail = _document(client, _lot(client, ("guia.png", image_bytes(), "image/png")))
    required = {f["field_name"] for f in detail["fields"] if f["is_required"]}
    assert required == {"PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE"}


def test_failed_extraction_is_retried_in_a_new_run(client, fake_ai):
    fake_ai.pages = {1: page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "1"), quality="BAJA")}
    fake_ai.extractions = [AIError("OpenRouter respondió 502: proveedor caído", "PROVEEDOR")]
    lot = _lot(client, ("factura.png", image_bytes(), "image/png"))
    assert lot["status"] == "COMPLETADO_CON_ERRORES"
    failed = _document(client, lot)
    assert (failed["run"]["technical_status"], failed["run"]["error_code"]) == ("FALLIDO", "PROVEEDOR")
    assert failed["steps"][0]["status"] == "ERROR"

    client.post(f"/submissions/{lot['id']}/process")
    detail = _document(client, client.get(f"/submissions/{lot['id']}").json())
    assert [r["run_number"] for r in detail["history"]] == [1, 2]
    assert detail["run"]["run_number"] == 2 and detail["run"]["provider_rut"] == "76123456-0"
    # La alerta de la segmentación se conserva en el nuevo procesamiento
    assert [i["code"] for i in detail["issues"]] == ["BAJA_CALIDAD_IMAGEN"]
    # La página no se volvió a clasificar
    assert len(fake_ai.calls) == 1


def test_quota_during_extraction_stops_the_lot(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [AIError("Se agotó el límite diario", "CUOTA")]
    lot = _lot(client, ("a.png", image_bytes(10, 10), "image/png"), ("b.png", image_bytes(20, 20), "image/png"))
    assert lot["status"] == "COMPLETADO_CON_ERRORES"
    assert len(fake_ai.calls) == 1  # el segundo archivo ni se clasificó
