"""Normalizador (código, sin IA): convierte el texto leído por la IA en valores exactos.

Cada función recibe el texto tal como aparece en el documento y devuelve el valor normalizado, o
None con el motivo si no se puede interpretar con seguridad. Nunca adivina: un formato dudoso
deja el campo ILEGIBLE, con el texto original guardado para revisarlo.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.core.config import settings
from app.models.enums import SUBSTITUTE_RUT


@dataclass
class Parsed:
    value: object | None
    reason: str | None = None


def _plain(text: str) -> str:
    """Sin tildes, mayúsculas y espacios simples."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().upper()


def _doubtful(raw: str) -> bool:
    """La IA marca con ? lo que no pudo leer con seguridad."""
    return "?" in raw


# --- RUT -------------------------------------------------------------------------------------


def rut_check_digit(body: int) -> str:
    """Dígito verificador del RUT chileno (módulo 11)."""
    total, factor = 0, 2
    for digit in reversed(str(body)):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    rest = 11 - total % 11
    return {11: "0", 10: "K"}.get(rest, str(rest))


def parse_rut(raw: str) -> Parsed:
    """'R.U.T.: 76.123.456-k' → '76123456-K'. Exige un dígito verificador correcto."""
    if _doubtful(raw):
        return Parsed(None, "tiene caracteres que no se leyeron con seguridad")
    text = re.sub(r"^(R\.?\s*U\.?\s*T\.?|RUT)\s*:?\s*", "", _plain(raw))
    compact = re.sub(r"[\s.]", "", text)
    match = re.fullmatch(r"(\d{1,8})-?([\dK])", compact)
    if not match:
        return Parsed(None, f"formato de RUT no reconocido: {raw!r}")
    body, check = int(match.group(1)), match.group(2)
    if body == 0:
        return Parsed(None, "RUT sin número")
    expected = rut_check_digit(body)
    if check != expected:
        return Parsed(None, f"el dígito verificador no corresponde (es {check}, debería ser {expected})")
    return Parsed(f"{body}-{check}")


# --- Número del documento --------------------------------------------------------------------


def parse_document_number(raw: str) -> Parsed:
    """'N° 001234' → '001234'; 'N° 2.397' → '2397'. Conserva los ceros iniciales: son parte de su identidad."""
    if _doubtful(raw):
        return Parsed(None, "tiene caracteres que no se leyeron con seguridad")
    text = re.sub(r"^\s*(N\s*[°ºO]\s*\.?|NRO\.?|NUM\.?|NUMERO|FOLIO|#)\s*:?\s*", "", raw.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s+", "", text)
    # Algunos documentos imprimen el número con punto de miles (2.397): el punto no es parte del número
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")
    if not re.fullmatch(r"[0-9A-Za-z\-]{1,40}", text) or not re.search(r"\d", text):
        return Parsed(None, f"número de documento no reconocido: {raw!r}")
    return Parsed(text)


# --- Fecha -----------------------------------------------------------------------------------

_MONTHS = {
    "ENE": 1, "ENERO": 1, "FEB": 2, "FEBRERO": 2, "MAR": 3, "MARZO": 3, "ABR": 4, "ABRIL": 4,
    "MAY": 5, "MAYO": 5, "JUN": 6, "JUNIO": 6, "JUL": 7, "JULIO": 7, "AGO": 8, "AGOSTO": 8,
    "SEP": 9, "SEPT": 9, "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCT": 10, "OCTUBRE": 10,
    "NOV": 11, "NOVIEMBRE": 11, "DIC": 12, "DICIEMBRE": 12,
}


def _full_year(year: int) -> int:
    return year + 2000 if year < 100 else year


def parse_date(raw: str, today: date | None = None) -> Parsed:
    """Formato chileno día/mes/año: '14/10/2026', '14-10-26', '14 de octubre de 2026', '14-OCT-2026'.

    También acepta ISO (2026-10-14). Nunca interpreta mes/día al revés.
    """
    if _doubtful(raw):
        return Parsed(None, "tiene caracteres que no se leyeron con seguridad")
    text = _plain(raw)
    text = re.sub(r"^(FECHA( DE)?( EMISION)?|EMISION)\s*:?\s*", "", text)
    parts = None
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text):
        parts = (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    elif m := re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2}|\d{4})", text):
        parts = (int(m.group(1)), int(m.group(2)), _full_year(int(m.group(3))))
    elif m := re.fullmatch(r"(\d{1,2})(?: DE |[\s\-/.]+)([A-Z]+)\.?(?: DE(L)? |[\s\-/.]+)(\d{2}|\d{4})", text):
        month = _MONTHS.get(m.group(2))
        if month:
            parts = (int(m.group(1)), month, _full_year(int(m.group(4))))
    if parts is None:
        return Parsed(None, f"formato de fecha no reconocido: {raw!r}")
    day, month, year = parts
    try:
        value = date(year, month, day)
    except ValueError:
        return Parsed(None, f"la fecha no existe: {raw!r}")
    today = today or date.today()
    if value.year < 2000 or value > today + timedelta(days=365):
        return Parsed(None, f"fecha fuera de rango: {value.isoformat()}")
    return Parsed(value)


# --- Montos ----------------------------------------------------------------------------------


def parse_amount(raw: str) -> Parsed:
    """Montos en pesos chilenos: '$ 1.190.000' → 1190000. El punto separa miles y la coma, decimales."""
    if _doubtful(raw):
        return Parsed(None, "tiene caracteres que no se leyeron con seguridad")
    text = re.sub(r"^(CLP|\$|PESOS)\s*|\s*(CLP|PESOS)$", "", raw.strip().upper()).replace("$", "")
    text = re.sub(r"\s+", "", text)
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", text):  # 1.190.000 o 1.190.000,50
        number = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+", text):  # 1,190,000 (separador de miles en inglés)
        number = text.replace(",", "")
    elif re.fullmatch(r"\d+(,\d{1,2})?", text):  # 1190000 o 1190000,50
        number = text.replace(",", ".")
    else:
        return Parsed(None, f"monto no reconocido: {raw!r}")
    return Parsed(Decimal(number))


# --- Normalización de una extracción completa ------------------------------------------------

PARSERS = {
    "PROVIDER_RUT": parse_rut,
    "DOCUMENT_NUMBER": parse_document_number,
    "ISSUE_DATE": parse_date,
    "NET_AMOUNT": parse_amount,
    "TAX_AMOUNT": parse_amount,
    "EXEMPT_AMOUNT": parse_amount,
    "TOTAL_AMOUNT": parse_amount,
}

FIELD_LABELS = {
    "PROVIDER_RUT": "RUT del prestador",
    "DOCUMENT_NUMBER": "Número del documento",
    "ISSUE_DATE": "Fecha de emisión",
    "NET_AMOUNT": "Monto neto",
    "TAX_AMOUNT": "Impuestos",
    "EXEMPT_AMOUNT": "Monto exento",
    "TOTAL_AMOUNT": "Monto total",
}


@dataclass
class NormalizedField:
    name: str
    status: str  # LEIDO, AUSENTE o ILEGIBLE
    value: object | None
    raw_text: str | None
    confidence: float | None
    region_index: int | None
    invalid_reason: str | None = None


@dataclass
class Normalized:
    fields: dict[str, NormalizedField]
    provider_rut: str | None
    rut_is_substitute: bool
    issues: list[dict] = field(default_factory=list)
    # IVA por separado (si hay una línea de IVA legible): permite comprobar el 19 % aunque haya otros impuestos
    vat_amount: Decimal | None = None


def normalize_field(name: str, status: str, raw_text: str | None, confidence: float | None, region_index: int | None) -> NormalizedField:
    raw = raw_text.strip() if raw_text and raw_text.strip() else None
    item = NormalizedField(name, status, None, raw, confidence, region_index)
    if status == "AUSENTE":
        item.raw_text = None
        return item
    if status == "ILEGIBLE":
        item.invalid_reason = "la IA no pudo leerlo con seguridad"
        return item
    if raw is None:
        item.status, item.invalid_reason = "ILEGIBLE", "marcado como leído pero sin texto"
        return item
    if confidence is not None and confidence < settings.FIELD_MIN_CONFIDENCE:
        item.status = "ILEGIBLE"
        item.invalid_reason = f"confianza {confidence:.2f}, por debajo del mínimo {settings.FIELD_MIN_CONFIDENCE:.2f}"
        return item
    parsed = PARSERS[name](raw)
    if parsed.value is None:
        item.status, item.invalid_reason = "ILEGIBLE", parsed.reason
        return item
    item.value = parsed.value
    return item


def normalize_tax_lines(lines: list[dict]) -> tuple[NormalizedField, Decimal | None]:
    """Impuestos = suma de todas las líneas (IVA, ILL, adicionales…). La suma la hace el código.

    Sin líneas: AUSENTE. Si alguna línea no se lee, el total de impuestos queda ILEGIBLE: sumar solo las
    legibles daría un monto falso. Devuelve también el IVA (la suma de las líneas cuyo nombre dice IVA).
    """
    if not lines:
        return NormalizedField("TAX_AMOUNT", "AUSENTE", None, None, None, None), None
    parsed = [
        (
            line.get("label") or "impuesto",
            normalize_field(
                "TAX_AMOUNT", line.get("status", "ILEGIBLE"), line.get("raw_text"),
                line.get("confidence"), line.get("region_index"),
            ),
        )
        for line in lines
    ]
    raw = " + ".join(f"{label}: {item.raw_text or '?'}" for label, item in parsed)
    confidences = [item.confidence for _, item in parsed if item.confidence is not None]
    region = next((item.region_index for _, item in parsed if item.region_index), None)
    result = NormalizedField("TAX_AMOUNT", "LEIDO", None, raw, min(confidences) if confidences else None, region)
    unreadable = [(label, item) for label, item in parsed if item.status != "LEIDO"]
    if unreadable:
        label, item = unreadable[0]
        result.status, result.invalid_reason = "ILEGIBLE", f"no se pudo leer {label} ({item.invalid_reason})"
        return result, None
    result.value = sum((item.value for _, item in parsed), Decimal(0))
    vat = [item.value for label, item in parsed if "IVA" in _plain(label)]
    return result, (sum(vat, Decimal(0)) if vat else None)


def _from_reading(name: str, fields: dict[str, dict]) -> NormalizedField:
    given = fields.get(name) or {"status": "AUSENTE"}
    if "lines" in given:
        return normalize_tax_lines(given["lines"])[0]
    return normalize_field(
        name, given.get("status", "AUSENTE"), given.get("raw_text"), given.get("confidence"), given.get("region_index")
    )


def reconcile(item: NormalizedField, second: NormalizedField) -> str | None:
    """Compara la lectura principal con una segunda lectura independiente del mismo documento.

    Un dato realmente legible se lee igual dos veces; uno que la IA "adivina" suele cambiar entre
    lecturas (por ejemplo, una fecha borrosa leída como 10-10-2025 y luego 18-10-2026). Si no
    coinciden, el campo pasa a ILEGIBLE. Nunca rescata un campo: si la principal no lo leyó, sigue igual.
    Devuelve el motivo si hubo desacuerdo (y modifica `item`).
    """
    reason = None
    if item.status == "LEIDO":
        if second.status != "LEIDO":
            reason = f"la segunda lectura no lo pudo leer ({second.raw_text or 'sin texto'})"
        elif second.value != item.value:
            reason = f"dos lecturas no coinciden ({item.raw_text!r} y {second.raw_text!r})"
    elif item.status == "AUSENTE" and second.status == "LEIDO":
        reason = f"una lectura no lo encontró y otra leyó {second.raw_text!r}"
    if reason:
        item.status, item.value, item.invalid_reason = "ILEGIBLE", None, reason
        if item.confidence is not None and second.confidence is not None:
            item.confidence = min(item.confidence, second.confidence)
    return reason


def normalize_extraction(fields: dict[str, dict], check: dict[str, dict] | None = None) -> Normalized:
    """`fields`: por campo, {status, raw_text, confidence, region_index} como los devuelve el extractor.

    `check`: una segunda lectura independiente (misma forma). Si se da, los campos en los que las
    dos lecturas no coinciden quedan ILEGIBLE con la alerta LECTURA_INCONSISTENTE.
    TAX_AMOUNT puede venir como {"lines": [...]} (cada línea de impuesto): se suma con normalize_tax_lines.
    """
    result: dict[str, NormalizedField] = {}
    issues: list[dict] = []
    for name in PARSERS:
        item = _from_reading(name, fields)
        result[name] = item
        if check is not None:
            second = _from_reading(name, check)
            reason = reconcile(item, second)
            if reason:
                issues.append(
                    {
                        "code": "LECTURA_INCONSISTENTE",
                        "severity": "ADVERTENCIA",
                        "field_name": name,
                        "message": f"{FIELD_LABELS[name]} no fiable: {reason}.",
                        "details": {"first": item.raw_text, "second": second.raw_text},
                    }
                )
                continue
        if item.status == "ILEGIBLE" and name != "PROVIDER_RUT":
            issues.append(
                {
                    "code": "CAMPO_ILEGIBLE",
                    "severity": "ADVERTENCIA",
                    "field_name": name,
                    "message": f"{FIELD_LABELS[name]} ilegible: {item.invalid_reason}"
                    + (f" (leído: {item.raw_text!r})" if item.raw_text else ""),
                    "details": {"raw_text": item.raw_text, "confidence": item.confidence},
                }
            )
        if isinstance(item.value, Decimal) and item.value != item.value.to_integral_value():
            issues.append(
                {
                    "code": "MONTO_CON_DECIMALES",
                    "severity": "ADVERTENCIA",
                    "field_name": name,
                    "message": f"{FIELD_LABELS[name]} con decimales ({item.raw_text}); en pesos chilenos se esperan enteros.",
                    "details": {"raw_text": item.raw_text},
                }
            )

    rut = result["PROVIDER_RUT"]
    substitute = rut.status != "LEIDO"
    if substitute:
        # La especificación exige 1-9 cuando el RUT no se puede recuperar; el indicador evita
        # confundirlo con un RUT real
        reason = "no aparece en el documento" if rut.status == "AUSENTE" else rut.invalid_reason
        issues.append(
            {
                "code": "RUT_SUSTITUTO",
                "severity": "ERROR",
                "field_name": "PROVIDER_RUT",
                "message": f"RUT del prestador no recuperable ({reason}); se guardó {SUBSTITUTE_RUT}.",
                "details": {"raw_text": rut.raw_text, "confidence": rut.confidence},
            }
        )
    vat = None
    tax_given = fields.get("TAX_AMOUNT") or {}
    if "lines" in tax_given and result["TAX_AMOUNT"].status == "LEIDO":
        vat = normalize_tax_lines(tax_given["lines"])[1]
    return Normalized(
        fields=result,
        provider_rut=SUBSTITUTE_RUT if substitute else rut.value,
        rut_is_substitute=substitute,
        issues=issues,
        vat_amount=vat,
    )
