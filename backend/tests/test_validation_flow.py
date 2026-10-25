"""Validación, estados y persistencia de punta a punta (con IA simulada y base de datos real)."""
from app.ai.client import AIError
from tests.factories import detected, extraction, image_bytes, page_response, reading

INVOICE = page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "000123"))


def _lot(client, *files):
    created = client.post("/submissions", files=[("files", f) for f in files]).json()
    return client.get(f"/submissions/{created['id']}").json()


def _detail(client, document_id):
    return client.get(f"/documents/{document_id}").json()


def test_spec_cases_end_to_end(client, fake_ai):
    """Una imagen por caso: correcto, descuadre, ilegible, desconocido y opcional ausente."""
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [
        extraction(),
        extraction(TOTAL_AMOUNT=reading("$ 120.000")),
        extraction(
            PROVIDER_RUT=reading("76.1??.456-0", status="ILEGIBLE", confidence=0.3),
            ISSUE_DATE=reading("0?/10/2026", status="ILEGIBLE", confidence=0.3),
        ),
        extraction(DOCUMENT_NUMBER=reading("N° 4"), notes="sin exento ni otros impuestos"),
    ]
    files = [(f"{n}.png", image_bytes(10 + n, 10), "image/png") for n in range(4)]
    lot = _lot(client, *files)
    assert lot["status"] == "COMPLETADO"
    statuses = [d["overall_status"] for d in lot["documents"]]
    assert statuses == ["PROCESADO", "DESCUADRE", "NO_LEGIBLE", "PROCESADO"]

    mismatch = _detail(client, lot["documents"][1]["id"])["run"]
    assert (float(mismatch["calculated_total"]), float(mismatch["difference"])) == (119000, 1000)
    assert mismatch["is_current"] and mismatch["finished_at"]

    illegible = _detail(client, lot["documents"][2]["id"])["run"]
    assert (illegible["provider_rut"], illegible["rut_is_substitute"], illegible["issue_date"]) == ("1-9", True, None)
    assert illegible["validation_status"] == "CUADRA"


def test_unknown_image_is_stored_without_accounting_data(client, fake_ai):
    # Caso 4: se conserva la imagen y la clasificación; no se extrae nada
    (document,) = _lot(client, ("foto.jpg", image_bytes(fmt="JPEG"), "image/jpeg"))["documents"]
    detail = _detail(client, document["id"])
    assert (detail["run"]["overall_status"], detail["run"]["total_amount"], detail["fields"]) == ("DESCONOCIDO", None, [])
    assert fake_ai.extraction_calls == []
    page = detail["regions"][0]["page_id"]
    assert client.get(f"/pages/{page}/image").status_code == 200


def test_same_invoice_photographed_twice_is_flagged_as_possible_duplicate(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    first = _lot(client, ("foto1.jpg", image_bytes(400, 300, fmt="JPEG"), "image/jpeg"))
    second = _lot(client, ("foto2.jpg", image_bytes(401, 300, fmt="JPEG"), "image/jpeg"))  # otra foto
    assert _detail(client, first["documents"][0]["id"])["issues"] == []
    issues = _detail(client, second["documents"][0]["id"])["issues"]
    assert [i["code"] for i in issues] == ["POSIBLE_DUPLICADO"]


def test_substitute_rut_is_never_a_duplicate(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    unreadable = extraction(PROVIDER_RUT=reading("??", status="ILEGIBLE", confidence=0.1))
    fake_ai.extractions = [unreadable, unreadable]
    _lot(client, ("a.png", image_bytes(10, 10), "image/png"))
    lot = _lot(client, ("b.png", image_bytes(11, 10), "image/png"))
    codes = [i["code"] for i in _detail(client, lot["documents"][0]["id"])["issues"]]
    assert "POSIBLE_DUPLICADO" not in codes


def test_reprocessing_replaces_the_current_result_and_keeps_history(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(TOTAL_AMOUNT=reading("$ 120.000")), extraction()]
    lot = _lot(client, ("f.png", image_bytes(), "image/png"))
    document_id = lot["documents"][0]["id"]
    assert lot["documents"][0]["overall_status"] == "DESCUADRE"

    response = client.post(f"/documents/{document_id}/reprocess")
    assert response.status_code == 202 and response.json()["run_number"] == 2
    detail = _detail(client, document_id)
    assert (detail["run"]["run_number"], detail["run"]["overall_status"]) == (2, "PROCESADO")
    assert [(r["run_number"], r["is_current"]) for r in detail["history"]] == [(1, False), (2, True)]


def test_failed_reprocessing_keeps_the_previous_result(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(), AIError("OpenRouter respondió 502", "PROVEEDOR")]
    lot = _lot(client, ("f.png", image_bytes(), "image/png"))
    document_id = lot["documents"][0]["id"]

    client.post(f"/documents/{document_id}/reprocess")
    detail = _detail(client, document_id)
    assert (detail["run"]["run_number"], detail["run"]["overall_status"]) == (1, "PROCESADO")
    assert [(r["run_number"], r["technical_status"]) for r in detail["history"]] == [(1, "COMPLETADO"), (2, "FALLIDO")]
    # El lote sigue mostrando el resultado vigente
    lot = client.get(f"/submissions/{lot['id']}").json()
    assert lot["documents"][0]["overall_status"] == "PROCESADO"


def test_reprocess_rules(client, fake_ai):
    (unknown,) = _lot(client, ("x.png", image_bytes(), "image/png"))["documents"]
    assert client.post(f"/documents/{unknown['id']}/reprocess").status_code == 409
    assert client.post("/documents/00000000-0000-0000-0000-000000000000/reprocess").status_code == 404


def test_document_inbox_lists_current_results_with_filters(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(), extraction(DOCUMENT_NUMBER=reading("N° 999"), TOTAL_AMOUNT=reading("$ 120.000"))]
    _lot(client, ("a.png", image_bytes(10, 10), "image/png"), ("b.png", image_bytes(11, 10), "image/png"))
    fake_ai.pages = {}
    _lot(client, ("c.png", image_bytes(12, 10), "image/png"))  # desconocido

    items = client.get("/documents").json()
    assert len(items) == 3 and all(i["first_page_id"] for i in items)
    mismatch = client.get("/documents", params={"status": "DESCUADRE"}).json()
    assert [(i["document_number"], i["issue_count"]) for i in mismatch] == [("999", 1)]
    assert len(client.get("/documents", params={"q": "76.123.456"}).json()) == 2  # RUT con o sin puntos
    assert [i["document_number"] for i in client.get("/documents", params={"q": "999"}).json()] == ["999"]
    assert len(client.get("/documents", params={"doc_type": "DESCONOCIDO"}).json()) == 1

    stats = client.get("/documents/stats").json()
    assert stats["total"] == 3
    assert stats["by_status"] == {"PROCESADO": 1, "DESCUADRE": 1, "DESCONOCIDO": 1}
    assert stats["by_type"] == {"FACTURA_ELECTRONICA": 2, "DESCONOCIDO": 1}


def test_second_reading_disagreement_makes_the_document_not_legible(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(ISSUE_DATE=reading("10.10.2025", confidence=0.9))]
    fake_ai.verifications = [extraction(ISSUE_DATE=reading("18-10-2026", confidence=0.8))]
    lot = _lot(client, ("borrosa.png", image_bytes(), "image/png"))
    detail = _detail(client, lot["documents"][0]["id"])
    assert detail["run"]["overall_status"] == "NO_LEGIBLE" and detail["run"]["issue_date"] is None
    assert [s["step"] for s in detail["steps"]][:2] == ["EXTRACCION", "VERIFICACION"]
    assert "LECTURA_INCONSISTENTE" in [i["code"] for i in detail["issues"]]


def test_failed_second_reading_does_not_accept_the_data(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.verifications = [AIError("OpenRouter respondió 502", "PROVEEDOR")]
    lot = _lot(client, ("f.png", image_bytes(), "image/png"))
    detail = _detail(client, lot["documents"][0]["id"])
    assert detail["run"]["technical_status"] == "FALLIDO"
    assert [(s["step"], s["status"]) for s in detail["steps"]] == [("EXTRACCION", "OK"), ("VERIFICACION", "ERROR")]


def test_verification_can_be_disabled(client, fake_ai, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "EXTRACTION_VERIFY", False)
    fake_ai.pages = {1: INVOICE}
    lot = _lot(client, ("f.png", image_bytes(), "image/png"))
    assert fake_ai.verification_calls == 0
    assert lot["documents"][0]["overall_status"] == "PROCESADO"


def test_signature_is_stored_as_true_or_false(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(signed=True), extraction(DOCUMENT_NUMBER=reading("N° 2"))]
    lot = _lot(client, ("firmada.png", image_bytes(10, 10), "image/png"), ("sin-firma.png", image_bytes(11, 10), "image/png"))
    signed, unsigned = lot["documents"]
    assert (signed["has_signature"], unsigned["has_signature"]) == (True, False)
    run = _detail(client, signed["id"])["run"]
    assert run["has_signature"] is True and float(run["signature_confidence"]) == 0.9
    assert client.get("/documents").json()[0]["has_signature"] in (True, False)


def test_signature_seen_by_only_one_reading_is_not_accepted(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(signed=True)]
    fake_ai.verifications = [extraction(signed=False)]
    lot = _lot(client, ("dudosa.png", image_bytes(), "image/png"))
    detail = _detail(client, lot["documents"][0]["id"])
    assert detail["run"]["has_signature"] is False
    assert "FIRMA_DUDOSA" in [i["code"] for i in detail["issues"]]
    # La firma no afecta al estado del documento
    assert detail["run"]["overall_status"] == "PROCESADO"


def test_unknown_documents_have_no_signature_analysis(client, fake_ai):
    (document,) = _lot(client, ("x.png", image_bytes(), "image/png"))["documents"]
    assert document["has_signature"] is None


def test_hidden_additional_tax_makes_the_document_not_legible(client, fake_ai):
    from tests.factories import tax_line

    fake_ai.pages = {1: page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO/FALTANTE", "1.352.386"))}
    fake_ai.extractions = [
        extraction(
            DOCUMENT_NUMBER=reading("N° 1.352.386"),
            NET_AMOUNT=reading("$ 2.267"),
            TOTAL_AMOUNT=reading("$ 2.925"),
            tax_lines=[tax_line("431"), tax_line("?", label="ILL(10,0%)", status="ILEGIBLE", confidence=0.1)],
        )
    ]
    lot = _lot(client, ("faltante.png", image_bytes(), "image/png"))
    run = _detail(client, lot["documents"][0]["id"])["run"]
    assert (run["overall_status"], run["validation_status"], run["other_taxes_amount"]) == ("NO_LEGIBLE", "INCOMPLETA", None)
    assert float(run["vat_amount"]) == 431  # el IVA sí se leyó
    assert run["document_number"] == "1352386"


def test_illegible_net_stores_every_amount_as_zero(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(NET_AMOUNT=reading("$ 1?0.000", status="ILEGIBLE", confidence=0.2))]
    lot = _lot(client, ("neto_tapado.png", image_bytes(), "image/png"))
    detail = _detail(client, lot["documents"][0]["id"])
    run = detail["run"]
    assert run["overall_status"] == "NO_LEGIBLE"
    assert {float(run[c]) for c in ("net_amount", "vat_amount", "total_amount")} == {0}
    assert "MONTOS_EN_CERO" in [i["code"] for i in detail["issues"]]
    # Lo leído queda en el detalle de campos
    net = next(f for f in detail["fields"] if f["field_name"] == "NET_AMOUNT")
    assert (net["status"], net["raw_text"]) == ("ILEGIBLE", "$ 1?0.000")
