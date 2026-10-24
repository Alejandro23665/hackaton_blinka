"""Validador (código puro, sin IA ni base de datos): reglas de negocio sobre los datos normalizados.

- Campos obligatorios según el tipo de documento.
- Suma: neto + impuestos + exento = total, con la tolerancia configurada.
- Alertas que no cambian el estado (IVA distinto del 19 %).
- Estado general derivado: DESCONOCIDO → NO_LEGIBLE → DESCUADRE → PROCESADO.

La aritmética usa Decimal: exacta, sin errores de redondeo de los float.
"""
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

REQUIRED_FIELDS = ("PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE", "NET_AMOUNT", "TOTAL_AMOUNT")
AMOUNT_FIELDS = ("NET_AMOUNT", "TAX_AMOUNT", "EXEMPT_AMOUNT", "TOTAL_AMOUNT")
VAT_RATE = Decimal("0.19")
# Diferencia admitida entre el IVA leído y el 19 % del neto (redondeo del documento)
VAT_TOLERANCE = Decimal(1)

LABELS = {
    "PROVIDER_RUT": "RUT del prestador",
    "DOCUMENT_NUMBER": "número del documento",
    "ISSUE_DATE": "fecha de emisión",
    "NET_AMOUNT": "monto neto",
    "TAX_AMOUNT": "impuestos",
    "EXEMPT_AMOUNT": "monto exento",
    "TOTAL_AMOUNT": "monto total",
}


def is_unvalued_guide(doc_type: str, statuses: dict[str, str]) -> bool:
    """Guía de despacho sin ningún monto (traslado sin valorizar): es válida sin montos."""
    return doc_type == "GUIA_DESPACHO" and all(statuses[name] == "AUSENTE" for name in AMOUNT_FIELDS)


def required_fields(doc_type: str, statuses: dict[str, str]) -> set[str]:
    """Obligatorios según el tipo. `statuses`: estado (LEIDO, AUSENTE, ILEGIBLE) de cada campo."""
    if is_unvalued_guide(doc_type, statuses):
        return {"PROVIDER_RUT", "DOCUMENT_NUMBER", "ISSUE_DATE"}
    return set(REQUIRED_FIELDS)


def clp(amount: Decimal) -> str:
    """$ 1.190.000 (formato chileno), para los mensajes."""
    sign = "-" if amount < 0 else ""
    decimals = 0 if amount == amount.to_integral_value() else 2
    text = f"{abs(amount):,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}$ {text}"


@dataclass
class Validation:
    extraction_status: str
    validation_status: str
    overall_status: str
    calculated_total: Decimal | None
    difference: Decimal | None
    review_reason: str | None
    issues: list[dict] = field(default_factory=list)


def validate(doc_type: str, statuses: dict[str, str], values: dict[str, object], tolerance: Decimal) -> Validation:
    """`statuses` y `values`: estado y valor normalizado de cada campo (None si no hay valor)."""
    issues: list[dict] = []
    reasons: list[str] = []

    # 1. Obligatorios
    required = required_fields(doc_type, statuses)
    missing = [name for name in REQUIRED_FIELDS if name in required and statuses[name] != "LEIDO"]
    extraction_status = "INCOMPLETA" if missing else "COMPLETA"
    for name in missing:
        if statuses[name] == "AUSENTE" and name != "PROVIDER_RUT":  # los ilegibles ya tienen su alerta
            issues.append(
                {
                    "code": "CAMPO_OBLIGATORIO_AUSENTE",
                    "severity": "ERROR",
                    "field_name": name,
                    "message": f"Falta un dato obligatorio: {LABELS[name]} no aparece en el documento.",
                    "details": None,
                }
            )
    if missing:
        reasons.append("No se pudo recuperar: " + ", ".join(LABELS[name] for name in missing))

    # 2. Suma de montos
    net, tax, exempt, total = (values[name] for name in AMOUNT_FIELDS)
    calculated = difference = None
    if is_unvalued_guide(doc_type, statuses):
        validation_status = "NO_APLICA"
    else:
        unknown = [name for name in ("NET_AMOUNT", "TOTAL_AMOUNT") if values[name] is None]
        unknown += [name for name in ("TAX_AMOUNT", "EXEMPT_AMOUNT") if statuses[name] == "ILEGIBLE"]
        if unknown:
            validation_status = "INCOMPLETA"
            message = "No se pudo comprobar la suma: falta " + ", ".join(LABELS[name] for name in unknown)
            reasons.append(message)
            issues.append(
                {
                    "code": "VALIDACION_INCOMPLETA",
                    "severity": "INFO",
                    "field_name": None,
                    "message": message + ".",
                    "details": {"fields": unknown},
                }
            )
        else:
            # Un opcional ausente no suma (no es lo mismo que 0, pero no aporta al total)
            calculated = net + (tax or Decimal(0)) + (exempt or Decimal(0))
            difference = total - calculated
            if abs(difference) > tolerance:
                validation_status = "DESCUADRE"
                parts = [f"neto {clp(net)}"]
                parts += [f"impuestos {clp(tax)}"] if tax is not None else []
                parts += [f"exento {clp(exempt)}"] if exempt is not None else []
                message = (
                    f"Descuadre: {' + '.join(parts)} = {clp(calculated)}, pero el total declarado es "
                    f"{clp(total)} (diferencia {clp(difference)})."
                )
                reasons.append(message.rstrip("."))
                issues.append(
                    {
                        "code": "DESCUADRE",
                        "severity": "ERROR",
                        "field_name": "TOTAL_AMOUNT",
                        "message": message,
                        "details": {"calculated": str(calculated), "declared": str(total), "difference": str(difference)},
                    }
                )
            else:
                validation_status = "CUADRA"

    # 3. Alertas que no cambian el estado
    if doc_type == "FACTURA_ELECTRONICA" and net is not None and tax is not None:
        expected = (net * VAT_RATE).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        if abs(tax - expected) > VAT_TOLERANCE:
            issues.append(
                {
                    "code": "IVA_NO_CORRESPONDE_19",
                    "severity": "ADVERTENCIA",
                    "field_name": "TAX_AMOUNT",
                    "message": f"Los impuestos ({clp(tax)}) no son el 19 % del neto ({clp(expected)}): "
                    "puede haber otros impuestos o una lectura errónea.",
                    "details": {"expected_vat": str(expected), "tax": str(tax)},
                }
            )

    # 4. Estado general. Un opcional ilegible que impide comprobar la suma también es NO_LEGIBLE:
    #    marcarlo PROCESADO ocultaría que el total no se pudo verificar.
    if extraction_status == "INCOMPLETA" or validation_status == "INCOMPLETA":
        overall = "NO_LEGIBLE"
    elif validation_status == "DESCUADRE":
        overall = "DESCUADRE"
    else:
        overall = "PROCESADO"

    return Validation(
        extraction_status=extraction_status,
        validation_status=validation_status,
        overall_status=overall,
        calculated_total=calculated,
        difference=difference,
        review_reason=". ".join(reasons) + "." if reasons else None,
        issues=issues,
    )
