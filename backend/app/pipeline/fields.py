"""Campos que lee el extractor. Los nombres son internos del procesamiento: al guardar se pasan a
las columnas de documentos_procesados (ver app/pipeline/process.py)."""

FIELD_NAMES = (
    "PROVIDER_RUT",
    "DOCUMENT_NUMBER",
    "ISSUE_DATE",
    "NET_AMOUNT",
    # IVA: obligatorio. Otros impuestos (IABA, ILA…) y exento: opcionales
    "VAT_AMOUNT",
    "OTHER_TAXES_AMOUNT",
    "EXEMPT_AMOUNT",
    "TOTAL_AMOUNT",
)

# Valor que se guarda cuando el RUT no se puede leer de forma fiable
SUBSTITUTE_RUT = "1-9"
