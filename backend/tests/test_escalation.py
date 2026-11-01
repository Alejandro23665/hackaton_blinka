"""Cuándo un documento va a revisión humana, el RUT de cada tipo y la boleta más legible (sin base de datos ni IA)."""
import pytest

from app.pipeline.extractor import Extraction
from app.pipeline.grouper import GroupedDocument, GroupedRegion
from app.pipeline.normalize import split_tax_lines
from app.pipeline.process import build_reading, escalation_reasons, less_legible, row_values
from app.pipeline.ruts import fits, read_digits
from tests.factories import ABSENT, extraction, reading, tax_line


def _extraction(covered=False, catalog=None, **fields):
    data = extraction(**fields)
    return Extraction.model_validate({**data, "attached_sheet_covers_data": covered, "catalog_rut": catalog})


def _reading(doc_type="FACTURA_ELECTRONICA", title="FACTURA ELECTRÓNICA", covered=False, catalog=None, **fields):
    data = _extraction(covered, catalog, **fields)
    return build_reading(doc_type, data, data, title=title)


def _row(**kwargs):
    return row_values(_reading(**kwargs))


# --- Revisión humana: solo descuadres confirmados y dudas de clasificación ----------------------


def test_correct_invoice_is_not_escalated():
    row = _row()
    assert (row["observaciones"], row["escalado"]) == ("LEGIBLE", False)


def test_confirmed_mismatch_is_escalated():
    row = _row(TOTAL_AMOUNT=reading("$ 120.000"))
    assert (row["observaciones"], row["escalado"]) == ("DESCUADRE", True)


@pytest.mark.parametrize(
    "fields",
    [
        {"ISSUE_DATE": reading("1?/10/2026", status="ILEGIBLE", confidence=0.3)},
        {"DOCUMENT_NUMBER": ABSENT},
        {"NET_AMOUNT": ABSENT},  # 2 de los 3 montos: la suma no se puede comprobar
        {"NET_AMOUNT": ABSENT, "VAT_AMOUNT": ABSENT, "TOTAL_AMOUNT": ABSENT},
        {"PROVIDER_RUT": reading("12.3??", status="ILEGIBLE", confidence=0.3)},  # factura sin RUT recuperable
        {"DOCUMENT_NUMBER": reading("N° 000123", confidence=0.7)},  # confianza baja
        {"NET_AMOUNT": reading("$ 100.000,50")},  # decimales: mala lectura
    ],
)
def test_unreadable_data_alone_is_not_escalated(fields):
    row = _row(**fields)
    assert row["escalado"] is False and row["observaciones"] in ("LEGIBLE", "NO_LEGIBLE")


def test_unreadable_extra_tax_is_not_deduced_nor_escalated():
    row = _row(tax_lines=[tax_line("$ 19.000"), tax_line("$ ?.000", label="ILA 31.5%", status="ILEGIBLE", confidence=0.4)])
    assert (row["observaciones"], row["escalado"], row["impuestos"]) == ("NO_LEGIBLE", False, None)


def test_missing_amount_keeps_every_amount_at_zero():
    row = _row(NET_AMOUNT=ABSENT)
    assert (row["total_neto"], row["iva"], row["total"]) == (0, 0, 0)


def test_low_confidence_value_is_kept_as_doubtful():
    row = _row(DOCUMENT_NUMBER=reading("N° 000123", confidence=0.7))
    assert row["folio"] == "000123" and "folio" in row["campos_dudosos"]


def test_inferred_type_is_escalated():
    reading_ = _reading()
    reading_.type_inferred = True
    assert escalation_reasons(reading_) == ["tipo deducido sin ver el título"]


# --- Hoja adjunta que tapa un dato clave --------------------------------------------------------


def test_attached_sheet_covering_data_drops_every_amount_without_escalating():
    row = _row(covered=True)
    assert (row["observaciones"], row["escalado"]) == ("NO_LEGIBLE", False)
    assert (row["total_neto"], row["iva"], row["total"], row["impuestos"]) == (0, 0, 0, 0)
    assert row["folio"] == "000123" and row["rut_proveedor"] == "76123456-0"  # lo demás se conserva


# --- Retención ----------------------------------------------------------------------------------


def test_retention_is_an_extra_tax_not_vat():
    vat, others = split_tax_lines([{"label": "IVA 19%"}, {"label": "Ret. IVA"}, {"label": "Retención"}])
    assert [line["label"] for line in vat] == ["IVA 19%"]
    assert [line["label"] for line in others] == ["Ret. IVA", "Retención"]
    row = _row(
        tax_lines=[tax_line("$ 19.000"), tax_line("$ 1.000", label="Retención")],
        TOTAL_AMOUNT=reading("$ 120.000"),
    )
    assert (row["iva"], row["impuestos"], row["observaciones"]) == (19000, 1000, "LEGIBLE")


# --- RUT ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rut",
    [reading("R.U.T. 76.084.682", confidence=0.9), ABSENT, reading("76.123.456-0")],
)
def test_control_interno_always_gets_its_fixed_rut(rut):
    # El caso de la imagen ("76.084.682" sin verificador), sin RUT visible y con otro RUT leído
    row = _row(doc_type="CONTROL_INTERNO", title="CONTROL INTERNO", PROVIDER_RUT=rut)
    assert (row["rut_proveedor"], row["observaciones"], row["escalado"]) == ("76084682-1", "LEGIBLE", False)


@pytest.mark.parametrize(
    "title, rut, denomination",
    [
        ("GUÍA DE DESPACHO", "94851000-6", "GUIA_DESPACHO"),
        ("GUIA ELECTRONICA", "76084682-1", "GUIA_ELECTRONICA"),
        ("GUÍA DE DESPACHO ELECTRÓNICA", "76084682-1", "GUIA_ELECTRONICA"),
    ],
)
def test_guide_rut_depends_on_its_denomination(title, rut, denomination):
    row = _row(doc_type="GUIA_DESPACHO", title=title, PROVIDER_RUT=ABSENT)
    assert (row["rut_proveedor"], row["denominacion"], row["escalado"]) == (rut, denomination, False)


def test_guide_without_visible_denomination_only_takes_a_fitting_rut():
    assert _row(doc_type="GUIA_DESPACHO", title="Ing. Guías Manuales", PROVIDER_RUT=ABSENT)["rut_proveedor"] == "1-9"
    fitting = reading("94.851.000", status="ILEGIBLE", confidence=0.5)
    assert _row(doc_type="GUIA_DESPACHO", title=None, PROVIDER_RUT=fitting)["rut_proveedor"] == "94851000-6"


def test_invoice_rut_missing_digits_is_completed_from_the_catalog():
    row = _row(PROVIDER_RUT=reading("93.178.000-?", status="ILEGIBLE", confidence=0.5))
    assert (row["rut_proveedor"], row["escalado"]) == ("93178000-K", False)


def test_invoice_with_new_valid_rut_is_accepted():
    assert _row(PROVIDER_RUT=reading("76.123.456-0"))["rut_proveedor"] == "76123456-0"


def test_catalog_proposal_needs_both_readings_and_no_contradicting_digits():
    blurred = reading("9?.???.???-?", status="ILEGIBLE", confidence=0.3)
    assert _row(PROVIDER_RUT=blurred, catalog="99.501.760-1")["rut_proveedor"] == "99501760-1"
    # Una sola lectura lo propone: no basta
    first = _extraction(catalog="99501760-1", PROVIDER_RUT=blurred)
    second = _extraction(catalog=None, PROVIDER_RUT=blurred)
    assert row_values(build_reading("FACTURA_ELECTRONICA", first, second, "FACTURA"))["rut_proveedor"] == "1-9"
    # Los dígitos visibles lo contradicen
    other = reading("88.5??.???-?", status="ILEGIBLE", confidence=0.3)
    assert _row(PROVIDER_RUT=other, catalog="99501760-1")["rut_proveedor"] == "1-9"
    # Un RUT fuera del catálogo nunca se acepta como propuesta
    assert _row(PROVIDER_RUT=blurred, catalog="76123456-0")["rut_proveedor"] == "1-9"


def test_rut_fits_known_one_only_with_at_most_two_missing_digits():
    assert fits(read_digits("76.084.682"), "76084682-1")
    assert fits(read_digits("7608468"), "76084682-1")  # faltan 2
    assert not fits(read_digits("760846"), "76084682-1")  # faltan 3
    assert not fits(read_digits("76.084.682-7"), "76084682-1")  # verificador distinto
    assert read_digits("R.U.T.: 93.178.000-k") == "93178000K"


# --- Varias boletas en la misma imagen ------------------------------------------------------------


def _document(page=1, pages=1):
    regions = [GroupedRegion(page + i, 1, None, None) for i in range(pages)]
    return GroupedDocument("CONTROL_INTERNO", 0.9, "CONTROL INTERNO", None, regions)


def test_only_the_most_legible_document_of_a_page_is_kept():
    clear = _reading(doc_type="CONTROL_INTERNO", title="CONTROL INTERNO")
    blurry = _reading(doc_type="CONTROL_INTERNO", title="CONTROL INTERNO", ISSUE_DATE=ABSENT, NET_AMOUNT=ABSENT)
    found = [_document(), _document(), _document(page=2)]
    assert less_legible(found, {0: blurry, 1: clear, 2: blurry}) == {0}
    # Un documento de varias páginas no compite
    assert less_legible([_document(pages=2), _document()], {0: blurry, 1: clear}) == set()


def test_attached_sheet_needs_both_readings_to_drop_the_amounts():
    first, second = _extraction(covered=True), _extraction(covered=False)
    row = row_values(build_reading("FACTURA_ELECTRONICA", first, second, "FACTURA ELECTRÓNICA"))
    assert (row["total_neto"], row["total"], row["observaciones"]) == (100000, 119000, "LEGIBLE")
