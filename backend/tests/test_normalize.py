"""Normalizador: del texto leído por la IA a valores exactos. Sin base de datos ni IA."""
from datetime import date
from decimal import Decimal

import pytest

from app.core.config import settings
from app.pipeline.normalize import (
    normalize_extraction,
    parse_amount,
    parse_date,
    parse_document_number,
    parse_rut,
    rut_check_digit,
)
from app.pipeline.validate import required_fields
from tests.factories import ABSENT, extraction, readings, reading, tax_line

TODAY = date(2026, 10, 24)


def fields(**kwargs):
    """Lecturas por campo de una extracción simulada, listas para normalize_extraction."""
    return readings(extraction(**kwargs))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("76.123.456-0", "76123456-0"),
        ("R.U.T.: 76.123.456-0", "76123456-0"),
        ("76123456-0", "76123456-0"),
        ("12.345.678-5", "12345678-5"),
        ("8.765.401-k", "8765401-K"),  # dígito verificador K, en minúscula
    ],
)
def test_valid_ruts(raw, expected):
    assert parse_rut(raw).value == expected


@pytest.mark.parametrize("raw", ["76.123.456-K", "76.12?.456-0", "RUT", "123456789012-3", "0-0"])
def test_invalid_ruts(raw):
    parsed = parse_rut(raw)
    assert parsed.value is None and parsed.reason


def test_check_digit_examples():
    # Casos con dígito 0 y K, los más propensos a errores
    assert rut_check_digit(76123456) == "0"
    assert rut_check_digit(1) == "9"
    assert any(rut_check_digit(n) == "K" for n in range(1, 50))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("14/10/2026", date(2026, 10, 14)),
        ("14-10-26", date(2026, 10, 14)),
        ("05.03.2026", date(2026, 3, 5)),
        ("14 de octubre de 2026", date(2026, 10, 14)),
        ("14-OCT-2026", date(2026, 10, 14)),
        ("3 sept. 2026", date(2026, 9, 3)),
        ("2026-10-14", date(2026, 10, 14)),
        ("Fecha de emisión: 05/03/2026", date(2026, 3, 5)),
    ],
)
def test_dates_are_day_month_year(raw, expected):
    assert parse_date(raw, today=TODAY).value == expected


@pytest.mark.parametrize("raw", ["31/02/2026", "0?/03/2026", "marzo", "05/03/2030", "14/10/1990", "2026/14/10"])
def test_invalid_dates(raw):
    assert parse_date(raw, today=TODAY).value is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$ 1.190.000", Decimal(1190000)),
        ("1.190.000", Decimal(1190000)),
        ("1190000", Decimal(1190000)),
        ("$119.000", Decimal(119000)),
        ("1,190,000", Decimal(1190000)),
        ("119.000,50", Decimal("119000.50")),
        ("0", Decimal(0)),
        ("CLP 5.000", Decimal(5000)),
    ],
)
def test_amounts_in_chilean_pesos(raw, expected):
    assert parse_amount(raw).value == expected


@pytest.mark.parametrize("raw", ["12.34", "1?0.000", "-5.000", "cien mil", "1.19.000"])
def test_invalid_amounts(raw):
    assert parse_amount(raw).value is None


def test_document_number_keeps_leading_zeros():
    assert parse_document_number("N° 001234").value == "001234"
    assert parse_document_number("Nº 8841").value == "8841"
    assert parse_document_number("Folio: 000552").value == "000552"
    assert parse_document_number("00?123").value is None
    # Punto de miles, como en los controles internos de OXXO
    assert parse_document_number("N° 2.397").value == "2397"
    assert parse_document_number("1.234.567").value == "1234567"
    assert parse_document_number("12.34").value is None


def test_absent_is_not_zero_and_illegible_keeps_original_text():
    result = normalize_extraction(
        fields(
            EXEMPT_AMOUNT=ABSENT,
            ISSUE_DATE=reading("0?/03/2026", status="ILEGIBLE", confidence=0.3),
        )
    )
    exempt, issue_date = result.fields["EXEMPT_AMOUNT"], result.fields["ISSUE_DATE"]
    assert (exempt.status, exempt.value) == ("AUSENTE", None)
    assert (issue_date.status, issue_date.value, issue_date.raw_text) == ("ILEGIBLE", None, "0?/03/2026")
    assert [i["code"] for i in result.issues] == ["CAMPO_ILEGIBLE"]


def test_low_confidence_or_unparseable_reading_becomes_illegible():
    result = normalize_extraction(
        fields(
            NET_AMOUNT=reading("$ 100.000", confidence=settings.FIELD_MIN_CONFIDENCE - 0.05),
            TOTAL_AMOUNT=reading("ciento diecinueve mil"),
        )
    )
    assert result.fields["NET_AMOUNT"].status == "ILEGIBLE" and "confianza" in result.fields["NET_AMOUNT"].invalid_reason
    assert result.fields["TOTAL_AMOUNT"].status == "ILEGIBLE"
    assert result.fields["TOTAL_AMOUNT"].raw_text == "ciento diecinueve mil"


@pytest.mark.parametrize(
    "rut",
    [reading("76.123.456-K"), reading("76.1??.456-0", status="ILEGIBLE", confidence=0.2), ABSENT],
)
def test_unrecoverable_rut_is_stored_as_substitute(rut):
    result = normalize_extraction(fields(PROVIDER_RUT=rut))
    assert (result.provider_rut, result.rut_is_substitute) == ("1-9", True)
    assert result.issues[0]["code"] == "RUT_SUSTITUTO"


def test_real_rut_is_not_substitute():
    result = normalize_extraction(fields())
    assert (result.provider_rut, result.rut_is_substitute, result.issues) == ("76123456-0", False, [])


def test_decimal_amount_is_flagged():
    result = normalize_extraction(fields(VAT_AMOUNT=reading("19.000,40")))
    assert result.fields["VAT_AMOUNT"].value == Decimal("19000.40")
    assert [i["code"] for i in result.issues] == ["MONTO_CON_DECIMALES"]


def test_required_fields_depend_on_document_type():
    valued = {
        "NET_AMOUNT": "LEIDO",
        "VAT_AMOUNT": "LEIDO",
        "OTHER_TAXES_AMOUNT": "AUSENTE",
        "EXEMPT_AMOUNT": "AUSENTE",
        "TOTAL_AMOUNT": "LEIDO",
    }
    unvalued = dict.fromkeys(valued, "AUSENTE")
    assert "NET_AMOUNT" in required_fields("FACTURA_ELECTRONICA", unvalued)
    assert "NET_AMOUNT" in required_fields("GUIA_DESPACHO", valued)
    assert required_fields("GUIA_DESPACHO", unvalued) == {"PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE"}


# --- Segunda lectura (verificación) -----------------------------------------------------------


def test_matching_second_reading_keeps_the_fields():
    first = fields()
    # Mismo dato escrito de otra forma: lo que se compara es el valor normalizado
    second = fields(ISSUE_DATE=reading("14/10/2026"), DOCUMENT_NUMBER=reading("000123"))
    result = normalize_extraction(first, second)
    assert all(f.status != "ILEGIBLE" for f in result.fields.values()) and result.issues == []


def test_guessed_date_that_changes_between_readings_becomes_illegible():
    # Caso real: fecha diminuta y borrosa leída como 10.10.2025 con 90 % de "confianza"
    first = fields(ISSUE_DATE=reading("10.10.2025", confidence=0.9))
    second = fields(ISSUE_DATE=reading("18-10-2026", confidence=0.8))
    result = normalize_extraction(first, second)
    date_field = result.fields["ISSUE_DATE"]
    assert (date_field.status, date_field.value, date_field.raw_text) == ("ILEGIBLE", None, "10.10.2025")
    assert "no coinciden" in date_field.invalid_reason
    assert [i["code"] for i in result.issues] == ["LECTURA_INCONSISTENTE"]
    assert result.issues[0]["details"] == {"first": "10.10.2025", "second": "18-10-2026"}


def test_second_reading_that_cannot_read_or_find_the_field_is_a_disagreement():
    unreadable = normalize_extraction(
        fields(), fields(TOTAL_AMOUNT=reading("1?9.000", status="ILEGIBLE", confidence=0.3))
    )
    assert unreadable.fields["TOTAL_AMOUNT"].status == "ILEGIBLE"
    found_once = normalize_extraction(fields(), fields(EXEMPT_AMOUNT=reading("$ 5.000")))
    assert found_once.fields["EXEMPT_AMOUNT"].status == "ILEGIBLE"
    assert "no lo encontró" in found_once.fields["EXEMPT_AMOUNT"].invalid_reason


def test_second_reading_never_rescues_a_field():
    first = fields(ISSUE_DATE=reading("0?/10/2026", status="ILEGIBLE", confidence=0.3))
    result = normalize_extraction(first, fields())
    assert result.fields["ISSUE_DATE"].status == "ILEGIBLE"


def test_inconsistent_rut_becomes_substitute():
    result = normalize_extraction(fields(), fields(PROVIDER_RUT=reading("76.123.465-K")))
    assert (result.provider_rut, result.rut_is_substitute) == ("1-9", True)
    assert sorted(i["code"] for i in result.issues) == ["LECTURA_INCONSISTENTE", "RUT_SUSTITUTO"]


# --- Impuestos: IVA aparte y otros impuestos sumados -----------------------------------------


def test_vat_and_other_taxes_are_separate_fields():
    result = normalize_extraction(
        fields(tax_lines=[tax_line("$ 431"), tax_line("$ 227", label="ILA VIN 20.5%"), tax_line("$ 100", label="IABA 10%")])
    )
    vat, other = result.fields["VAT_AMOUNT"], result.fields["OTHER_TAXES_AMOUNT"]
    assert (vat.status, vat.value, vat.raw_text) == ("LEIDO", Decimal(431), "IVA 19%: $ 431")
    assert (other.status, other.value) == ("LEIDO", Decimal(327))
    assert other.raw_text == "ILA VIN 20.5%: $ 227 + IABA 10%: $ 100"


def test_one_unreadable_additional_tax_makes_other_taxes_illegible_but_not_vat():
    # Caso real: el ILL tapado por una perforación; sumar solo los legibles daría un monto falso
    result = normalize_extraction(
        fields(tax_lines=[tax_line("431"), tax_line("?", label="ILL(10,0%)", status="ILEGIBLE", confidence=0.2)])
    )
    assert (result.fields["VAT_AMOUNT"].status, result.fields["VAT_AMOUNT"].value) == ("LEIDO", Decimal(431))
    other = result.fields["OTHER_TAXES_AMOUNT"]
    assert (other.status, other.value) == ("ILEGIBLE", None) and "ILL(10,0%)" in other.invalid_reason


def test_no_tax_lines_means_both_absent():
    result = normalize_extraction(fields(tax_lines=[]))
    assert result.fields["VAT_AMOUNT"].status == result.fields["OTHER_TAXES_AMOUNT"].status == "AUSENTE"


def test_two_matching_readings_accept_lower_confidence():
    # Las dos lecturas ven "$ 830" con 70 % de seguridad: coinciden, así que se acepta
    low = reading("$ 100.000", confidence=0.7)
    result = normalize_extraction(fields(NET_AMOUNT=low), fields(NET_AMOUNT=low))
    assert (result.fields["NET_AMOUNT"].status, result.fields["NET_AMOUNT"].value) == ("LEIDO", 100000)
    # Si no coinciden, sigue siendo ilegible
    other = reading("$ 106.000", confidence=0.7)
    result = normalize_extraction(fields(NET_AMOUNT=low), fields(NET_AMOUNT=other))
    assert result.fields["NET_AMOUNT"].status == "ILEGIBLE"
    # Por debajo del mínimo de coincidencia, tampoco
    very_low = reading("$ 100.000", confidence=settings.AGREEMENT_MIN_CONFIDENCE - 0.1)
    result = normalize_extraction(fields(NET_AMOUNT=very_low), fields(NET_AMOUNT=very_low))
    assert result.fields["NET_AMOUNT"].status == "ILEGIBLE"
