"""Validador: obligatorios, suma, alertas y estado general. Código puro: sin base de datos ni IA."""
from datetime import date
from decimal import Decimal

from app.pipeline.validate import validate

ZERO = Decimal(0)


def _case(doc_type="FACTURA_ELECTRONICA", tolerance=ZERO, **overrides):
    """Factura correcta: 100.000 + 19.000 = 119.000. Cada campo: (estado, valor)."""
    fields = {
        "PROVIDER_RUT": ("LEIDO", "76123456-0"),
        "DOCUMENT_NUMBER": ("LEIDO", "000123"),
        "ISSUE_DATE": ("LEIDO", date(2026, 10, 14)),
        "NET_AMOUNT": ("LEIDO", Decimal(100000)),
        "VAT_AMOUNT": ("LEIDO", Decimal(19000)),
        "OTHER_TAXES_AMOUNT": ("AUSENTE", None),
        "EXEMPT_AMOUNT": ("AUSENTE", None),
        "TOTAL_AMOUNT": ("LEIDO", Decimal(119000)),
    }
    fields.update(overrides)
    statuses = {name: status for name, (status, _) in fields.items()}
    values = {name: value for name, (_, value) in fields.items()}
    return validate(doc_type, statuses, values, tolerance)


def _codes(result):
    return [i["code"] for i in result.issues]


ILLEGIBLE = ("ILEGIBLE", None)
ABSENT = ("AUSENTE", None)


# --- Los 5 casos de la especificación -----------------------------------------------------------


def test_case_1_correct_document_is_processed():
    result = _case()
    assert (result.extraction_status, result.validation_status, result.overall_status) == ("COMPLETA", "CUADRA", "PROCESADO")
    assert (result.calculated_total, result.difference, result.review_reason, result.issues) == (
        Decimal(119000), ZERO, None, []
    )


def test_case_2_mismatch_stores_calculated_total_and_difference():
    result = _case(TOTAL_AMOUNT=("LEIDO", Decimal(120000)))
    assert (result.validation_status, result.overall_status) == ("DESCUADRE", "DESCUADRE")
    assert (result.calculated_total, result.difference) == (Decimal(119000), Decimal(1000))
    assert _codes(result) == ["DESCUADRE"]
    assert "$ 119.000" in result.review_reason and "$ 120.000" in result.review_reason


def test_case_3_partially_illegible_is_not_legible_but_keeps_the_rest():
    result = _case(PROVIDER_RUT=ILLEGIBLE, ISSUE_DATE=ILLEGIBLE)
    assert (result.extraction_status, result.overall_status) == ("INCOMPLETA", "NO_LEGIBLE")
    # Los montos sí se pudieron comprobar
    assert result.validation_status == "CUADRA" and result.calculated_total == Decimal(119000)
    assert "RUT del prestador" in result.review_reason and "fecha de emisión" in result.review_reason


def test_case_5_absent_optional_fields_are_not_errors():
    # Otros impuestos y exento ausentes: no suman y no son error
    result = _case(OTHER_TAXES_AMOUNT=ABSENT, EXEMPT_AMOUNT=ABSENT)
    assert (result.overall_status, result.calculated_total, result.issues) == ("PROCESADO", Decimal(119000), [])


def test_vat_is_required():
    result = _case(VAT_AMOUNT=ABSENT, TOTAL_AMOUNT=("LEIDO", Decimal(100000)))
    assert (result.extraction_status, result.overall_status) == ("INCOMPLETA", "NO_LEGIBLE")
    assert "CAMPO_OBLIGATORIO_AUSENTE" in _codes(result) and "IVA" in result.review_reason


def test_other_taxes_are_added_to_the_sum():
    result = _case(OTHER_TAXES_AMOUNT=("LEIDO", Decimal(20500)), TOTAL_AMOUNT=("LEIDO", Decimal(139500)))
    assert (result.validation_status, result.calculated_total) == ("CUADRA", Decimal(139500))


# (El caso 4, documento desconocido, no llega al validador: termina tras la clasificación.)


# --- Combinaciones y bordes ---------------------------------------------------------------------


def test_illegible_document_with_detectable_mismatch_keeps_both_results():
    result = _case(ISSUE_DATE=ILLEGIBLE, TOTAL_AMOUNT=("LEIDO", Decimal(120000)))
    assert result.overall_status == "NO_LEGIBLE"
    assert result.validation_status == "DESCUADRE" and result.difference == Decimal(1000)
    assert "DESCUADRE" in _codes(result)


def test_missing_amounts_never_produce_a_mismatch():
    result = _case(NET_AMOUNT=ILLEGIBLE)
    assert (result.validation_status, result.calculated_total, result.difference) == ("INCOMPLETA", None, None)
    assert "VALIDACION_INCOMPLETA" in _codes(result)


def test_illegible_optional_field_is_zero_when_the_rest_adds_up():
    # 100.000 + 19.000 ya es el total: el exento tapado solo puede ser 0
    result = _case(EXEMPT_AMOUNT=ILLEGIBLE)
    assert (result.extraction_status, result.validation_status, result.overall_status) == (
        "COMPLETA", "CUADRA", "PROCESADO"
    )
    assert result.amounts["EXEMPT_AMOUNT"] == ZERO and result.amounts["OTHER_TAXES_AMOUNT"] is None
    assert _codes(result) == ["OPCIONAL_DEDUCIDO"]


def test_illegible_optional_field_blocks_the_sum_check_when_the_rest_does_not_add_up():
    result = _case(OTHER_TAXES_AMOUNT=ILLEGIBLE, TOTAL_AMOUNT=("LEIDO", Decimal(121000)))
    assert result.extraction_status == "COMPLETA"
    assert (result.validation_status, result.overall_status) == ("INCOMPLETA", "NO_LEGIBLE")
    assert result.amounts["OTHER_TAXES_AMOUNT"] is None
    assert "otros impuestos" in result.review_reason


def test_missing_required_amount_sets_every_amount_to_zero():
    result = _case(NET_AMOUNT=ILLEGIBLE, EXEMPT_AMOUNT=("LEIDO", Decimal(500)))
    assert result.overall_status == "NO_LEGIBLE"
    assert set(result.amounts.values()) == {ZERO}
    assert "MONTOS_EN_CERO" in _codes(result)


def test_absent_vat_also_sets_every_amount_to_zero():
    result = _case(VAT_AMOUNT=ABSENT, TOTAL_AMOUNT=("LEIDO", Decimal(100000)))
    assert result.overall_status == "NO_LEGIBLE" and set(result.amounts.values()) == {ZERO}


def test_other_illegible_fields_keep_the_amounts():
    result = _case(ISSUE_DATE=ILLEGIBLE)
    assert result.overall_status == "NO_LEGIBLE" and result.amounts["TOTAL_AMOUNT"] == Decimal(119000)


def test_explicit_zero_is_a_value():
    result = _case(VAT_AMOUNT=("LEIDO", ZERO), EXEMPT_AMOUNT=("LEIDO", Decimal(19000)))
    assert (result.validation_status, result.calculated_total) == ("CUADRA", Decimal(119000))


def test_required_absent_field_is_reported():
    result = _case(DOCUMENT_NUMBER=ABSENT)
    assert result.overall_status == "NO_LEGIBLE"
    assert _codes(result) == ["CAMPO_OBLIGATORIO_AUSENTE"]


def test_unvalued_dispatch_guide_is_processed_without_sum():
    result = _case(
        "GUIA_DESPACHO", NET_AMOUNT=ABSENT, VAT_AMOUNT=ABSENT, EXEMPT_AMOUNT=ABSENT, TOTAL_AMOUNT=ABSENT
    )
    assert (result.extraction_status, result.validation_status, result.overall_status) == (
        "COMPLETA", "NO_APLICA", "PROCESADO"
    )
    # Guía sin valorizar: los montos siguen sin valor, no en 0
    assert set(result.amounts.values()) == {None}


def test_valued_dispatch_guide_requires_net_and_total():
    result = _case("GUIA_DESPACHO", NET_AMOUNT=ABSENT, VAT_AMOUNT=ABSENT)
    assert result.overall_status == "NO_LEGIBLE"


def test_tolerance_is_configurable():
    assert _case(TOTAL_AMOUNT=("LEIDO", Decimal(119001))).validation_status == "DESCUADRE"
    assert _case(tolerance=Decimal(1), TOTAL_AMOUNT=("LEIDO", Decimal(119001))).validation_status == "CUADRA"


def test_vat_different_from_19_percent_is_a_warning_not_a_mismatch():
    result = _case(VAT_AMOUNT=("LEIDO", Decimal(25000)), TOTAL_AMOUNT=("LEIDO", Decimal(125000)))
    assert result.overall_status == "PROCESADO"
    assert _codes(result) == ["IVA_NO_CORRESPONDE_19"]
    # Solo en facturas electrónicas
    other = _case("CONTROL_INTERNO", VAT_AMOUNT=("LEIDO", Decimal(25000)), TOTAL_AMOUNT=("LEIDO", Decimal(125000)))
    assert other.issues == []


def test_vat_check_ignores_other_taxes():
    # Neto 2.267: IVA 431 (19 %) + ILA 227 = 2.925
    result = _case(
        NET_AMOUNT=("LEIDO", Decimal(2267)),
        VAT_AMOUNT=("LEIDO", Decimal(431)),
        OTHER_TAXES_AMOUNT=("LEIDO", Decimal(227)),
        TOTAL_AMOUNT=("LEIDO", Decimal(2925)),
    )
    assert (result.overall_status, result.issues) == ("PROCESADO", [])


def test_unreadable_tax_line_is_zero_when_the_readable_lines_complete_the_total():
    # Neto 100.000 + IVA 19.000 + IABA legible 2.000 = 121.000 = total: la línea ilegible solo puede ser 0
    result = validate(
        "FACTURA_ELECTRONICA",
        {"PROVIDER_RUT": "LEIDO", "DOCUMENT_NUMBER": "LEIDO", "ISSUE_DATE": "LEIDO", "NET_AMOUNT": "LEIDO",
         "VAT_AMOUNT": "LEIDO", "OTHER_TAXES_AMOUNT": "ILEGIBLE", "EXEMPT_AMOUNT": "AUSENTE", "TOTAL_AMOUNT": "LEIDO"},
        {"PROVIDER_RUT": "76123456-0", "DOCUMENT_NUMBER": "1", "ISSUE_DATE": date(2026, 10, 14),
         "NET_AMOUNT": Decimal(100000), "VAT_AMOUNT": Decimal(19000), "OTHER_TAXES_AMOUNT": None,
         "EXEMPT_AMOUNT": None, "TOTAL_AMOUNT": Decimal(121000)},
        ZERO,
        partial={"OTHER_TAXES_AMOUNT": Decimal(2000)},
    )
    assert (result.overall_status, result.amounts["OTHER_TAXES_AMOUNT"]) == ("PROCESADO", Decimal(2000))
    assert "$ 2.000" in result.issues[0]["message"]
