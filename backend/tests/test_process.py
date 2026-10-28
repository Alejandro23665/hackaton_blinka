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


def _upload(client, *files, carpeta=None):
    """Sube y devuelve el trabajo terminado (en los tests, el segundo plano corre antes de responder)."""
    data = {"carpeta": carpeta} if carpeta is not None else None
    response = client.post("/trabajos", files=[("files", f) for f in files], data=data)
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
    # Lo procesó la IA, sin campos con problemas
    assert (doc["usuario"], doc["revisado_en"], doc["campos_faltantes"], doc["campos_dudosos"]) == ("Modelo IA", None, [], [])
    # El revisor puede ver el archivo original
    image = client.get(f"/documentos/{doc['id']}/imagen")
    assert image.status_code == 200 and image.headers["content-type"] == "image/png"


def test_mismatch_goes_to_human_review(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(TOTAL_AMOUNT=reading("$ 120.000"))]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["observaciones"], doc["requiere_revision"], doc["total"]) == ("DESCUADRE", True, 120000)
    assert doc["campos_dudosos"] == ["total_neto", "iva", "total"]


def test_illegible_required_amount_stores_zeros_and_goes_to_review(client, fake_ai):
    fake_ai.pages = {1: CONTROL}
    fake_ai.extractions = [extraction(NET_AMOUNT=reading("2.5??", status="ILEGIBLE", confidence=0.2))]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["observaciones"], doc["requiere_revision"]) == ("NO_LEGIBLE", True)
    assert (doc["total_neto"], doc["iva"], doc["impuestos"], doc["total"]) == (0, 0, 0, 0)
    # Se leyó algo ("2.5??"), pero no es fiable
    assert (doc["campos_faltantes"], doc["campos_dudosos"]) == ([], ["total_neto"])


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
    doc = _documents(client)[0]
    assert (doc["firma"], doc["campos_dudosos"]) == (False, ["firma"])


def test_second_reading_disagreement_makes_the_document_not_legible(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(ISSUE_DATE=reading("10.10.2025", confidence=0.9))]
    fake_ai.verifications = [extraction(ISSUE_DATE=reading("18-10-2026", confidence=0.8))]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["fecha"], doc["observaciones"], doc["campos_dudosos"]) == (None, "NO_LEGIBLE", ["fecha"])


def test_unvalued_dispatch_guide_is_legible_without_amounts(client, fake_ai):
    fake_ai.pages = {1: page_response(detected("GUIA_DESPACHO", "GUÍA DE DESPACHO ELECTRÓNICA", "55"))}
    fake_ai.extractions = [extraction(NET_AMOUNT=ABSENT, VAT_AMOUNT=ABSENT, TOTAL_AMOUNT=ABSENT)]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["observaciones"], doc["total_neto"], doc["iva"], doc["impuestos"], doc["total"]) == (
        "LEGIBLE", None, None, None, None
    )


def test_unavailable_ai_stops_the_whole_job(client, fake_ai):
    # Las lecturas de los 3 archivos van en la misma tanda: si la tanda no se puede enviar, nada se guarda
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(), AIError("Sin saldo en la API de Claude", "CUOTA")]
    job = _upload(client, _image(1), _image(2), _image(3))
    assert job["estado"] == "DETENIDO" and "Sin saldo" in job["mensaje"]
    assert [f["estado"] for f in job["archivos"]] == ["ERROR"] * 3
    assert _documents(client) == []


def test_all_files_of_a_job_share_the_same_batches(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(DOCUMENT_NUMBER=reading(f"N° {n}")) for n in (1, 2, 3)]
    job = _upload(client, _image(1), _image(2), _image(3))
    assert [d["resultado"] for f in job["archivos"] for d in f["documentos"]] == ["GUARDADO"] * 3
    # Una tanda para clasificar las 3 páginas y otra para las 6 lecturas
    assert fake_ai.batches == 2 and fake_ai.verification_calls == 3


def test_provider_error_on_one_document_does_not_stop_the_rest(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [AIError("Claude no procesó la solicitud: overloaded", "PROVEEDOR"), extraction(DOCUMENT_NUMBER=reading("N° 7"))]
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


def test_unreadable_and_absent_required_fields_are_missing(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(ISSUE_DATE=reading(None, status="ILEGIBLE"), DOCUMENT_NUMBER=ABSENT)]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["campos_faltantes"], doc["campos_dudosos"]) == (["folio", "fecha"], [])


def test_unreadable_other_tax_leaves_impuestos_empty_not_zero(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [
        extraction(
            EXEMPT_AMOUNT=reading("0"),
            TOTAL_AMOUNT=reading("$ 119.830"),
            tax_lines=[tax_line("19.000"), tax_line("8?0", label="IABA 10%", status="ILEGIBLE", confidence=0.3)],
        )
    ]
    _upload(client, _image())
    (doc,) = _documents(client)
    assert (doc["impuestos"], doc["observaciones"], doc["campos_dudosos"]) == (None, "NO_LEGIBLE", ["impuestos"])


def test_document_sharing_a_page_is_read_from_its_crop_and_the_full_page(client, fake_ai):
    fake_ai.pages = {
        1: page_response(
            detected("CONTROL_INTERNO", "CONTROL INTERNO", "1", region=LEFT),
            detected("CONTROL_INTERNO", "CONTROL INTERNO", "2", index=2, region=RIGHT),
        )
    }
    fake_ai.extractions = [extraction(DOCUMENT_NUMBER=reading("N° 1")), extraction(DOCUMENT_NUMBER=reading("N° 2"))]
    _upload(client, _image())
    assert [call["images"] for call in fake_ai.extraction_calls] == [2, 2]


def test_folder_upload_groups_its_documents(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(), extraction(DOCUMENT_NUMBER=reading("N° 2"))]
    job = _upload(client, ("Septiembre/1.png", *_image(1)[1:]), ("Septiembre/sub/2.png", *_image(2)[1:]), carpeta=" Septiembre ")
    assert job["carpeta"] == "Septiembre" and job["id_carpeta"] is not None
    docs = _documents(client, carpeta=job["id_carpeta"])
    assert {d["folio"] for d in docs} == {"000123", "2"}
    assert {(d["id_carpeta"], d["carpeta"]) for d in docs} == {(job["id_carpeta"], "Septiembre")}

    (folder,) = client.get("/carpetas").json()
    assert {k: folder[k] for k in ("id", "nombre", "usuario", "documentos", "requieren_revision")} == {
        "id": job["id_carpeta"], "nombre": "Septiembre", "usuario": "Rita Revisora", "documentos": 2, "requieren_revision": 0,
    }


def test_loose_files_have_no_folder_and_a_repeated_name_is_a_new_folder(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    loose = _upload(client, _image(1))
    assert loose["id_carpeta"] is None
    assert _documents(client)[0]["id_carpeta"] is None

    first = _upload(client, _image(2), carpeta="Agosto")
    second = _upload(client, _image(3), carpeta="Agosto")  # el mismo documento: queda como duplicado
    assert first["id_carpeta"] != second["id_carpeta"]
    assert second["archivos"][0]["documentos"][0]["resultado"] == "DUPLICADO"
    folders = client.get("/carpetas").json()
    assert [(f["nombre"], f["documentos"]) for f in folders] == [("Agosto", 0), ("Agosto", 0)]


def test_invalid_folder_upload_does_not_create_the_folder(client):
    response = client.post("/trabajos", files=[("files", ("a.txt", b"hola", "text/plain"))], data={"carpeta": "Mala"})
    assert response.status_code == 415
    assert client.get("/carpetas").json() == []


def test_a_folder_accepts_more_files_than_a_loose_upload(client, fake_ai, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_FILES_PER_SUBMISSION", 2)
    monkeypatch.setattr(settings, "MAX_FILES_PER_FOLDER", 3)
    fake_ai.pages = {1: INVOICE}
    three = [("files", _image(n)) for n in (1, 2, 3)]
    loose = client.post("/trabajos", files=three)
    assert loose.status_code == 422 and "carpeta" in loose.json()["detail"]
    assert client.post("/trabajos", files=three, data={"carpeta": "Grande"}).status_code == 202
    too_many = client.post("/trabajos", files=[*three, ("files", _image(4))], data={"carpeta": "Enorme"})
    assert too_many.status_code == 422 and "500" not in too_many.json()["detail"]
    assert [f["nombre"] for f in client.get("/carpetas").json()] == ["Grande"]
