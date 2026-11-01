"""RUT del emisor (código, sin IA): el fijo de cada tipo de documento y el catálogo de las facturas.

- Control interno: siempre 76084682-1, se lea o no (regla fija del tipo).
- Guías: una sola categoría, pero el RUT depende de la denominación impresa en el título. «Guía
  Electrónica» (también «Guía de Despacho Electrónica») → 76084682-1; «Guía de Despacho» → 94851000-6.
  Primero se identifica la denominación y después se asigna el RUT: el RUT nunca decide la denominación.
  Si el título no deja ver la denominación, el RUT solo se acepta si se lee o encaja con uno de los dos.
- Facturas: pueden tener distintos emisores. Un RUT completo y válido se acepta aunque no esté en el
  catálogo. Si no se lee entero, se normaliza a un RUT del catálogo cuando:
  · los dígitos leídos encajan con uno solo (mismo orden, faltando como máximo RUT_MAX_MISSING_DIGITS), o
  · las lecturas de la IA proponen el mismo RUT del catálogo (reconocido por el emisor y la presentación
    de la factura) y ninguna lectura lo contradice con los dígitos que ve.
- Nunca se elige un RUT arbitrariamente: con varios candidatos, o sin evidencia, el RUT queda no legible (1-9).
"""
import re
import unicodedata
from dataclasses import dataclass

from app.core.config import settings
from app.pipeline.normalize import NormalizedField

GUIA_ELECTRONICA = "GUIA_ELECTRONICA"
GUIA_DESPACHO = "GUIA_DESPACHO"


@dataclass
class RutResolution:
    value: str | None  # RUT final; None si no se pudo recuperar
    completed: str | None = None  # cómo se obtuvo, si no se leyó tal cual (para el aviso)


def _plain(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()


def guide_denomination(title: str | None) -> str | None:
    """Denominación de una guía según su título: «Electrónica» manda (también en «Guía de Despacho
    Electrónica»). None si el título no permite saberlo."""
    plain = _plain(title or "")
    if "ELECTRONICA" in plain:
        return GUIA_ELECTRONICA
    if "DESPACHO" in plain:
        return GUIA_DESPACHO
    return None


def expected_rut(doc_type: str, title: str | None) -> str | None:
    """El RUT fijo del tipo de documento; None si puede ser cualquiera (facturas) o si en una guía no se
    ve la denominación."""
    if doc_type == "CONTROL_INTERNO":
        return settings.CONTROL_INTERNO_RUT
    if doc_type == "GUIA_DESPACHO":
        return {
            GUIA_ELECTRONICA: settings.GUIA_ELECTRONICA_RUT,
            GUIA_DESPACHO: settings.GUIA_DESPACHO_RUT,
        }.get(guide_denomination(title))
    return None


def candidates_for(doc_type: str) -> list[str]:
    """RUT posibles cuando no hay un RUT fijo."""
    if doc_type == "GUIA_DESPACHO":
        return [settings.GUIA_ELECTRONICA_RUT, settings.GUIA_DESPACHO_RUT]
    if doc_type == "FACTURA_ELECTRONICA":
        return list(settings.KNOWN_INVOICE_RUTS)
    return []


def read_digits(raw: str | None) -> str:
    """Los dígitos (y la K del verificador) de lo que se leyó: 'R.U.T. 76.084.68?' → '7608468'."""
    if not raw:
        return ""
    text = re.sub(r"^\s*(R\.?\s*U\.?\s*T\.?|RUT)\s*:?", "", _plain(raw))
    return re.sub(r"[^0-9K]", "", text)


def _compact(rut: str) -> str:
    return rut.replace("-", "").replace(".", "").upper()


def _is_subsequence(part: str, whole: str) -> bool:
    remaining = iter(whole)
    return all(char in remaining for char in part)


def fits(digits: str, rut: str, max_missing: int | None = None) -> bool:
    """Los dígitos leídos encajan con el RUT (mismo orden), faltando como máximo `max_missing`
    (por defecto RUT_MAX_MISSING_DIGITS)."""
    max_missing = settings.RUT_MAX_MISSING_DIGITS if max_missing is None else max_missing
    target = _compact(rut)
    missing = len(target) - len(digits)
    return 0 <= missing <= max_missing and _is_subsequence(digits, target)


def resolve(
    doc_type: str,
    title: str | None,
    field: NormalizedField,
    raws: list[str | None],
    catalog_proposals: list[str | None] | None = None,
) -> RutResolution:
    """Decide el RUT del emisor. `field`: el RUT normalizado (LEIDO solo si es completo y válido);
    `raws`: lo que leyó cada lectura de la IA; `catalog_proposals`: el RUT del catálogo que propuso cada
    lectura (facturas)."""
    expected = expected_rut(doc_type, title)
    if expected is not None:
        if field.status == "LEIDO" and field.value == expected:
            return RutResolution(expected)
        return RutResolution(expected, completed="es el RUT fijo de este tipo de documento")
    if field.status == "LEIDO":
        return RutResolution(field.value)

    readings = [digits for digits in (read_digits(raw) for raw in raws) if digits]
    candidates = candidates_for(doc_type)
    matches = {rut for digits in readings for rut in candidates if fits(digits, rut)}
    if len(matches) == 1:
        return RutResolution(matches.pop(), completed="le faltaban dígitos; encaja con un único RUT conocido")

    # Propuesta de la IA: todas las lecturas proponen el mismo RUT del catálogo y ningún dígito leído lo contradice
    proposals = catalog_proposals or []
    known = {_compact(rut): rut for rut in settings.KNOWN_INVOICE_RUTS}
    proposed = {known.get(_compact(p)) if p else None for p in proposals}
    if doc_type == "FACTURA_ELECTRONICA" and proposals and len(proposed) == 1 and None not in proposed:
        rut = proposed.pop()
        if all(_is_subsequence(digits, _compact(rut)) for digits in readings):
            return RutResolution(rut, completed="reconocido en el catálogo de RUT conocidos por las dos lecturas")
    return RutResolution(None)
