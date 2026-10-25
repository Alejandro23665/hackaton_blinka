"""Comparación de la evaluación: correcto, omitido e inventado."""
from app.evaluation.compare import compare, report


def _doc(**overrides):
    base = {
        "tipo": "CONTROL_INTERNO", "estado": "PROCESADO", "rut": "76084682-1", "numero": "2397",
        "fecha": "2026-10-24", "neto": 22239, "iva": 4225, "otros_impuestos": None, "exento": 0,
        "total": 26464, "firma": True,
    }
    return {**base, **overrides}


def test_correct_omitted_and_invented_fields_are_counted():
    expected = [{"archivo": "1.png", "revisado": True, "documentos": [_doc(fecha=None)]}]
    system = {"1.png": {"documentos": [_doc(numero="002397", fecha="2026-10-10", iva=None)]}}
    totals = compare(expected, system)
    assert totals.fields["numero"]["correcto"] == 1  # los ceros iniciales no cambian el número
    assert totals.fields["iva"]["omitido"] == 1
    assert totals.fields["fecha"]["inventado"] == 1  # fecha ilegible que el sistema "leyó"
    assert totals.invented == [{"archivo": "1.png", "documento": 1, "campo": "fecha", "correcto": None, "sistema": "2026-10-10"}]
    assert "Datos inventados** | **1**" in report(totals, pending=0)


def test_document_count_and_type_mismatches():
    expected = [{"archivo": "2.png", "revisado": True, "documentos": [_doc(), _doc(tipo="GUIA_DESPACHO")]}]
    system = {"2.png": {"documentos": [_doc(tipo="DESCONOCIDO", estado="DESCONOCIDO")]}}
    totals = compare(expected, system)
    assert totals.images_with_count_mismatch == ["2.png"]
    assert (totals.type_correct, totals.type_total) == (0, 2)
    assert totals.invented == []  # con otro tipo, los campos no se comparan


def test_documents_are_paired_by_type_and_number_not_by_order():
    expected = [{"archivo": "57.png", "revisado": True, "documentos": [
        _doc(tipo="GUIA_DESPACHO", numero="2501600"), _doc(numero="2501600")]}]
    system = {"57.png": {"documentos": [_doc(numero="2.501.600"), _doc(tipo="GUIA_DESPACHO", numero="2501600")]}}
    totals = compare(expected, system)
    assert (totals.type_correct, totals.type_total) == (2, 2)
