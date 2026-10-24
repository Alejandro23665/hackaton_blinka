"""Valores permitidos de cada estado. Los usan los modelos (CHECK en la base) y el código.

Los valores van en español, como en la especificación: lo que se guarda es lo que ve el usuario.
"""

SUBMISSION_SOURCES = ("UPLOAD", "API")
SUBMISSION_STATUSES = ("RECIBIDO", "EN_PROCESO", "COMPLETADO", "COMPLETADO_CON_ERRORES")

PREPROCESS_STATUSES = ("PENDIENTE", "LISTO", "FALLIDO")

DOC_TYPES = ("GUIA_DESPACHO", "CONTROL_INTERNO", "FACTURA_ELECTRONICA", "DESCONOCIDO")

# Resultado de una llamada a la IA
CALL_STATUSES = ("OK", "ERROR")

# Dimensiones independientes del resultado de un procesamiento
TECHNICAL_STATUSES = ("EN_PROCESO", "COMPLETADO", "FALLIDO")
EXTRACTION_STATUSES = ("COMPLETA", "INCOMPLETA", "NO_APLICA")
VALIDATION_STATUSES = ("CUADRA", "DESCUADRE", "INCOMPLETA", "NO_APLICA")
OVERALL_STATUSES = ("PROCESADO", "NO_LEGIBLE", "DESCUADRE", "DESCONOCIDO")

FIELD_NAMES = (
    "PROVIDER_RUT",
    "DOCUMENT_NUMBER",
    "ISSUE_DATE",
    "NET_AMOUNT",
    "TAX_AMOUNT",
    "EXEMPT_AMOUNT",
    "TOTAL_AMOUNT",
)
FIELD_STATUSES = ("LEIDO", "AUSENTE", "ILEGIBLE")

ISSUE_SEVERITIES = ("ERROR", "ADVERTENCIA", "INFO")

RUN_STEPS = ("EXTRACCION", "VERIFICACION", "NORMALIZACION", "VALIDACION")
STEP_STATUSES = ("OK", "ERROR", "OMITIDO")

# Valor que exige la especificación cuando el RUT no se puede leer de forma fiable
SUBSTITUTE_RUT = "1-9"


def one_of(column: str, values: tuple[str, ...]) -> str:
    """Condición SQL para un CHECK: la columna solo admite esos valores."""
    allowed = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({allowed})"
