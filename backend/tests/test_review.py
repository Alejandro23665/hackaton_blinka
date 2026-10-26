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


def test_correction_is_saved_under_the_reviewer_and_leaves_the_queue(client, fake_ai):
    doc = _pending_document(client, fake_ai, NET_AMOUNT=reading("1?0.000", status="ILEGIBLE", confidence=0.2))
    assert (doc["usuario"], doc["total_neto"]) == ("Modelo IA", 0)

    response = client.put(f"/documentos/{doc['id']}/correccion", json=FIX)
    assert response.status_code == 200, response.text
    fixed = response.json()
    assert (fixed["usuario"], fixed["observaciones"], fixed["requiere_revision"]) == ("Rita Revisora", "LEGIBLE", False)
    assert (fixed["rut_proveedor"], fixed["total_neto"], fixed["firma"]) == ("76123456-0", 100000, True)
    assert fixed["revisado_en"] is not None
    # Lo que marcó la IA queda como registro
    assert fixed["campos_dudosos"] == ["total_neto"]
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
    assert "Faltan montos" in client.put(url, json={**FIX, "iva": None}).json()["detail"]
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
