"""Nombre de la imagen de cada documento: TIPO_RUT_FOLIO, con su archivo en documentos/."""
from app.pipeline.images import base_name
from app.storage import document_key, get_storage
from tests.factories import ABSENT, detected, extraction, image_bytes, page_response, reading

INVOICE = page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "000123"))
UNREADABLE_RUT = reading("76.1??.456-0", status="ILEGIBLE", confidence=0.3)


def _upload(client, n=1):
    client.post("/trabajos", files=[("files", (f"{n}.png", image_bytes(10 + n, 10), "image/png"))])


def _documents(client):
    return client.get("/documentos", params={"orden": "antiguos"}).json()["documentos"]


def test_name_format():
    assert base_name("FC", "93178000-K", "23193169") == "FC_93178000-K_23193169"
    assert base_name("FC", "1-9", "1458754") == "FC__1458754"  # RUT ilegible: se omite, nunca 1-9
    assert base_name("CI", "76084682-1", None) == "CI_76084682-1_"


def test_saved_document_gets_a_named_copy_of_its_image(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    _upload(client)
    (doc,) = _documents(client)
    assert doc["imagen"] == "FC_76123456-0_000123.png"
    assert get_storage().exists(document_key(doc["imagen"]))
    image = client.get(f"/documentos/{doc['id']}/imagen")
    assert image.status_code == 200 and 'filename="FC_76123456-0_000123.png"' in image.headers["content-disposition"]


def test_missing_data_leaves_its_part_empty_and_repeated_names_get_a_suffix(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(PROVIDER_RUT=UNREADABLE_RUT), extraction(PROVIDER_RUT=UNREADABLE_RUT)]
    _upload(client, 1)
    _upload(client, 2)  # otro documento con el mismo folio y RUT ilegible: mismo nombre base
    assert [d["imagen"] for d in _documents(client)] == ["FC__000123.png", "FC__000123-2.png"]


def test_document_without_folio(client, fake_ai):
    fake_ai.pages = {1: page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", None))}
    fake_ai.extractions = [extraction(DOCUMENT_NUMBER=ABSENT)]
    _upload(client)
    assert _documents(client)[0]["imagen"] == "CI_76123456-0_.png"


def test_correction_renames_the_image(client, fake_ai):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [extraction(PROVIDER_RUT=UNREADABLE_RUT)]
    _upload(client)
    (doc,) = _documents(client)
    assert doc["imagen"] == "FC__000123.png"
    fix = {
        "tipo": "FC", "rut_proveedor": "93.178.000-K", "folio": "23193169", "fecha": "2026-10-14", "firma": True,
        "total_neto": 100000, "iva": 19000, "impuestos": None, "total": 119000,
    }
    fixed = client.put(f"/documentos/{doc['id']}/correccion", json=fix).json()
    assert fixed["imagen"] == "FC_93178000-K_23193169.png"
    assert get_storage().exists(document_key(fixed["imagen"]))
    assert not get_storage().exists(document_key("FC__000123.png"))  # el nombre anterior ya no existe
    assert client.get(f"/documentos/{doc['id']}/imagen").status_code == 200
