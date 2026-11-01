"""Revisión humana: corrección de documentos y totales del día."""
from sqlalchemy import text

from tests.factories import detected, extraction, image_bytes, page_response, reading

INVOICE = page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "000123"))
FIX = {
    "tipo": "FC", "rut_proveedor": "76.123.456-0", "folio": "000123", "fecha": "2026-10-14", "firma": True,
    "total_neto": 100000, "iva": 19000, "impuestos": None, "total": 119000,
}


def _upload(client, n):
    client.post("/trabajos", files=[("files", (f"{n}.png", image_bytes(10 + n, 10), "image/png"))])


def _pending_document(client, fake_ai, **fields):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(**fields)]
    _upload(client, 1)
    (doc,) = client.get("/documentos", params={"requiere_revision": True}).json()["documentos"]
    return doc


# Un descuadre confirmado: va a revisión humana
MISMATCH = {"NET_AMOUNT": reading("$ 110.000")}


def test_correction_is_saved_under_the_reviewer_and_leaves_the_queue(client, fake_ai):
    doc = _pending_document(client, fake_ai, **MISMATCH)
    assert (doc["usuario"], doc["observaciones"], doc["total_neto"]) == ("Modelo IA", "DESCUADRE", 110000)

    response = client.put(f"/documentos/{doc['id']}/correccion", json=FIX)
    assert response.status_code == 200, response.text
    fixed = response.json()
    assert (fixed["usuario"], fixed["observaciones"], fixed["requiere_revision"]) == ("Rita Revisora", "LEGIBLE", False)
    assert (fixed["rut_proveedor"], fixed["total_neto"], fixed["firma"]) == ("76123456-0", 100000, True)
    assert fixed["revisado_en"] is not None
    # Lo que marcó la IA queda como registro
    assert fixed["campos_dudosos"] == ["total_neto", "iva", "total"]
    assert client.get("/documentos", params={"requiere_revision": True}).json()["total"] == 0


def test_correction_that_does_not_add_up_needs_confirmation(client, fake_ai):
    doc = _pending_document(client, fake_ai, TOTAL_AMOUNT=reading("$ 120.000"))
    url = f"/documentos/{doc['id']}/correccion"
    unconfirmed = client.put(url, json={**FIX, "total": 120000})
    assert unconfirmed.status_code == 422 and "diferencia 1000" in unconfirmed.json()["detail"]
    confirmed = client.put(url, json={**FIX, "total": 120000, "confirmar_descuadre": True}).json()
    assert (confirmed["observaciones"], confirmed["requiere_revision"]) == ("DESCUADRE", False)


def test_correction_rejects_invalid_data(client, fake_ai):
    doc = _pending_document(client, fake_ai, TOTAL_AMOUNT=reading("$ 120.000"))
    url = f"/documentos/{doc['id']}/correccion"
    assert "RUT no válido" in client.put(url, json={**FIX, "rut_proveedor": "76.123.456-1"}).json()["detail"]
    # Un monto que no se puede leer va vacío: la suma no se comprueba y queda NO_LEGIBLE
    assert client.put(url, json={**FIX, "iva": None}).json()["observaciones"] == "NO_LEGIBLE"
    assert client.put(url, json={**FIX, "total": -5}).status_code == 422
    # Una guía sin valorizar no lleva montos
    unvalued = {**FIX, "tipo": "GD", "total_neto": None, "iva": None, "total": None}
    assert client.put(url, json=unvalued).json()["observaciones"] == "LEGIBLE"


def test_correction_cannot_duplicate_another_document(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(), extraction(DOCUMENT_NUMBER=reading("N° 7"), TOTAL_AMOUNT=reading("$ 1"))]
    _upload(client, 1)
    _upload(client, 2)
    (pending,) = client.get("/documentos", params={"requiere_revision": True}).json()["documentos"]
    assert client.put(f"/documentos/{pending['id']}/correccion", json=FIX).status_code == 409  # mismo folio que el primero


def test_review_queue_lists_oldest_first(client, fake_ai, clean_db):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(DOCUMENT_NUMBER=reading(f"N° {n}"), TOTAL_AMOUNT=reading("$ 1")) for n in (1, 2)]
    _upload(client, 1)
    _upload(client, 2)
    with clean_db.begin() as conn:
        conn.execute(text("UPDATE documentos_procesados SET creado_en = now() - interval '1 day' WHERE folio = '1'"))
    queue = client.get("/documentos", params={"requiere_revision": True, "orden": "antiguos"}).json()["documentos"]
    assert [d["folio"] for d in queue] == ["1", "2"]


def test_day_totals(client, fake_ai, clean_db):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction()] + [
        extraction(DOCUMENT_NUMBER=reading(f"N° {n}"), TOTAL_AMOUNT=reading("$ 1")) for n in (2, 3, 4)
    ]
    for n in range(4):
        _upload(client, n)
    # Uno de los descuadres lo corrige una persona; otro es de ayer
    fixed = client.get("/documentos", params={"q": "2", "tipo": "FC"}).json()["documentos"]
    (fixed,) = [d for d in fixed if d["folio"] == "2"]
    assert client.put(f"/documentos/{fixed['id']}/correccion", json={**FIX, "folio": "2"}).status_code == 200
    with clean_db.begin() as conn:
        conn.execute(text("UPDATE documentos_procesados SET creado_en = now() - interval '1 day' WHERE folio = '4'"))

    today = client.get("/documentos/dia").json()
    assert {k: today[k] for k in ("registrados", "procesados_ia", "requieren_revision", "revisados", "pendientes_total")} == {
        "registrados": 3, "procesados_ia": 1, "requieren_revision": 1, "revisados": 1, "pendientes_total": 2,
    }
    assert client.get("/documentos/dia", params={"fecha": "2000-01-01"}).json()["registrados"] == 0


def test_accepting_keeps_the_data_and_leaves_the_queue(client, fake_ai):
    doc = _pending_document(client, fake_ai, **MISMATCH)
    response = client.post(f"/documentos/{doc['id']}/aceptar")
    assert response.status_code == 200, response.text
    accepted = response.json()
    # Nada cambia salvo quién lo revisó y cuándo
    unchanged = ("tipo", "rut_proveedor", "folio", "fecha", "total_neto", "total", "observaciones", "imagen", "campos_faltantes", "campos_dudosos")
    assert {k: accepted[k] for k in unchanged} == {k: doc[k] for k in unchanged}
    assert (accepted["usuario"], accepted["requiere_revision"]) == ("Rita Revisora", False)
    assert accepted["revisado_en"] is not None
    assert client.get("/documentos", params={"requiere_revision": True}).json()["total"] == 0
    assert client.post("/documentos/999/aceptar").status_code == 404


def test_correction_without_a_readable_date_is_saved_as_not_legible(client, fake_ai):
    doc = _pending_document(client, fake_ai, **MISMATCH)

    response = client.put(f"/documentos/{doc['id']}/correccion", json={**FIX, "fecha": None})
    assert response.status_code == 200, response.text
    fixed = response.json()
    assert (fixed["fecha"], fixed["observaciones"], fixed["requiere_revision"]) == (None, "NO_LEGIBLE", False)
    assert fixed["total_neto"] == 100000


def test_correction_can_leave_every_unreadable_field_empty(client, fake_ai):
    doc = _pending_document(client, fake_ai, **MISMATCH)
    empty = {**FIX, "rut_proveedor": None, "folio": "", "fecha": None, "total_neto": None, "iva": 19000, "total": None}

    response = client.put(f"/documentos/{doc['id']}/correccion", json=empty)
    assert response.status_code == 200, response.text
    fixed = response.json()
    # Como al procesar: RUT ilegible 1-9, folio y fecha sin valor; lo que sí se escribió se guarda
    assert (fixed["rut_proveedor"], fixed["folio"], fixed["fecha"]) == ("1-9", None, None)
    assert (fixed["total_neto"], fixed["iva"], fixed["total"]) == (None, 19000, None)
    assert (fixed["observaciones"], fixed["requiere_revision"], fixed["usuario"]) == ("NO_LEGIBLE", False, "Rita Revisora")
