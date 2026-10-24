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
        extraction(TAX_AMOUNT=reading(None, status="AUSENTE"), TOTAL_AMOUNT=reading("$ 100.000")),
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
