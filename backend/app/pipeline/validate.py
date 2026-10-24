"""Validador (código, sin IA): reglas de negocio sobre los datos normalizados.

Etapa actual: qué campos son obligatorios según el tipo de documento. La validación de montos y
el cálculo de estados se añaden en la etapa 5.4.
"""

REQUIRED_FIELDS = ("PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE", "NET_AMOUNT", "TOTAL_AMOUNT")
AMOUNT_FIELDS = ("NET_AMOUNT", "TAX_AMOUNT", "EXEMPT_AMOUNT", "TOTAL_AMOUNT")


def is_unvalued_guide(doc_type: str, statuses: dict[str, str]) -> bool:
    """Guía de despacho sin ningún monto (traslado sin valorizar): es válida sin montos."""
    return doc_type == "GUIA_DESPACHO" and all(statuses[name] == "AUSENTE" for name in AMOUNT_FIELDS)


def required_fields(doc_type: str, statuses: dict[str, str]) -> set[str]:
    """Obligatorios según el tipo. `statuses`: estado (LEIDO, AUSENTE, ILEGIBLE) de cada campo."""
    if is_unvalued_guide(doc_type, statuses):
        return {"PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE"}
    return set(REQUIRED_FIELDS)
