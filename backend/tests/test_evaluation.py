"""Comparación de la evaluación: correcto, omitido e inventado."""
from app.evaluation.compare import as_stored, compare, report


def _answer(**overrides):
    """Una respuesta como en muestras/respuestas.json."""
    base = {
        "tipo": "CONTROL_INTERNO", "estado": "PROCESADO", "rut": "76084682-1", "numero": "2397",
        "fecha": "2026-10-24", "neto": 22239, "iva": 4225, "otros_impuestos": None, "exento": 0,
        "total": 26464, "firma": True,
    }
    return {**base, **overrides}


def _stored(**overrides):
    """Lo que leyó el sistema, como en documentos_procesados."""
    return {**as_stored(_answer()), **overrides}


def test_answers_are_converted_to_the_stored_format():
    assert as_stored(_answer(otros_impuestos=98, exento=100)) == {
        "tipo": "CI", "estado": "LEGIBLE", "rut": "76084682-1", "numero": "2397", "fecha": "2026-10-24",
        "neto": 22239, "iva": 4225, "impuestos": 198, "total": 26464, "firma": True,
    }
    assert as_stored(_answer(otros_impuestos=None, exento=None))["impuestos"] is None
    assert as_stored(_answer(tipo="DESCONOCIDO", estado="DESCONOCIDO")) is None


def test_correct_omitted_and_invented_fields_are_counted():
    expected = [{"archivo": "1.png", "revisado": True, "documentos": [_answer(fecha=None)]}]
    system = {"1.png": {"documentos": [_stored(numero="002397", fecha="2026-10-10", iva=None)]}}
    totals = compare(expected, system)
    assert totals.fields["numero"]["correcto"] == 1  # los ceros iniciales no cambian el número
    assert totals.fields["iva"]["omitido"] == 1
    assert totals.fields["fecha"]["inventado"] == 1  # fecha ilegible que el sistema "leyó"
    assert totals.invented == [{"archivo": "1.png", "documento": 1, "campo": "fecha", "correcto": None, "sistema": "2026-10-10"}]
    assert "Datos inventados** | **1**" in report(totals, pending=0)


def test_unknown_documents_are_not_expected():
    expected = [{"archivo": "2.png", "revisado": True, "documentos": [_answer(), _answer(tipo="DESCONOCIDO", estado="DESCONOCIDO")]}]
    totals = compare(expected, {"2.png": {"documentos": [_stored()]}})
    assert (totals.documents_expected, totals.images_with_count_mismatch) == (1, [])


def test_document_count_and_type_mismatches():
    expected = [{"archivo": "2.png", "revisado": True, "documentos": [_answer(), _answer(tipo="GUIA_DESPACHO")]}]
    system = {"2.png": {"documentos": [_stored(tipo="FC")]}}
    totals = compare(expected, system)
    assert totals.images_with_count_mismatch == ["2.png"]
    assert (totals.type_correct, totals.type_total) == (0, 2)
    assert totals.invented == []  # con otro tipo, los campos no se comparan


def test_documents_are_paired_by_type_and_number_not_by_order():
    expected = [{"archivo": "57.png", "revisado": True, "documentos": [
        _answer(tipo="GUIA_DESPACHO", numero="2501600"), _answer(numero="2501600")]}]
    system = {"57.png": {"documentos": [_stored(numero="2.501.600"), _stored(tipo="GD", numero="2501600")]}}
    totals = compare(expected, system)
    assert (totals.type_correct, totals.type_total) == (2, 2)


def test_images_not_yet_processed_do_not_count_as_expected():
    expected = [{"archivo": "9.png", "revisado": True, "documentos": [_answer()]}]
    totals = compare(expected, {})
    assert (totals.documents_expected, [e["archivo"] for e in totals.errors]) == (0, ["9.png"])
