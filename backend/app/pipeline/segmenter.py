"""Agente A — Segmentador-clasificador (IA, una llamada por página).

Mira una página y dice qué documentos hay en ella, de qué tipo es cada uno y con qué evidencia
(el título impreso). El código revisa después su respuesta (`verify_type`): sin evidencia o con
poca confianza, el documento queda como DESCONOCIDO. La IA propone, el código decide.
"""
import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field

from app.ai import client
from app.core.config import settings

PROMPT_VERSION = "seg-5"

DocType = Literal["GUIA_DESPACHO", "CONTROL_INTERNO", "FACTURA_ELECTRONICA", "DESCONOCIDO"]


class Region(BaseModel):
    x: float
    y: float
    w: float
    h: float


class PageQuality(BaseModel):
    level: Literal["ALTA", "MEDIA", "BAJA"]
    issues: list[str] = Field(default_factory=list)


class DetectedDocument(BaseModel):
    index: int
    doc_type: DocType
    confidence: float = Field(ge=0, le=1)
    evidence: str | None
    document_number_seen: str | None
    continuation_of_previous: bool
    region: Region
    position_hint: str | None


class PageAnalysis(BaseModel):
    page_quality: PageQuality
    documents: list[DetectedDocument] = Field(min_length=1)


def _nullable(kind: str, description: str) -> dict:
    return {"type": [kind, "null"], "description": description}


def _number(description: str) -> dict:
    return {"type": "number", "description": description}


RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_quality", "documents"],
    "properties": {
        "page_quality": {
            "type": "object",
            "additionalProperties": False,
            "required": ["level", "issues"],
            "properties": {
                "level": {"type": "string", "enum": ["ALTA", "MEDIA", "BAJA"]},
                "issues": {"type": "array", "items": {"type": "string"}, "description": "Problemas visibles, en español"},
            },
        },
        "documents": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "index", "doc_type", "confidence", "evidence", "document_number_seen",
                    "continuation_of_previous", "region", "position_hint",
                ],
                "properties": {
                    "index": {"type": "integer", "description": "1, 2… de izquierda a derecha y de arriba abajo"},
                    "doc_type": {
                        "type": "string",
                        "enum": ["GUIA_DESPACHO", "CONTROL_INTERNO", "FACTURA_ELECTRONICA", "DESCONOCIDO"],
                    },
                    "confidence": _number("Seguridad en el tipo, de 0 a 1"),
                    "evidence": _nullable("string", "Copia literal del título impreso; null si no se ve"),
                    "document_number_seen": _nullable("string", "Número o folio tal como aparece; null si no se ve"),
                    "continuation_of_previous": {"type": "boolean"},
                    "region": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["x", "y", "w", "h"],
                        "properties": {
                            "x": _number("Borde izquierdo, 0 a 1"),
                            "y": _number("Borde superior, 0 a 1"),
                            "w": _number("Ancho, 0 a 1"),
                            "h": _number("Alto, 0 a 1"),
                        },
                    },
                    "position_hint": _nullable("string", "Ubicación en palabras: 'página completa', 'mitad izquierda'…"),
                },
            },
        },
    },
}

SYSTEM_PROMPT = """Eres el segmentador-clasificador de un sistema de captura de documentos tributarios \
chilenos. Recibes la imagen de UNA página de un lote escaneado o fotografiado y dices qué documentos \
aparecen en ella y de qué tipo es cada uno.

Tipos admitidos, solo si ves el título impreso en el documento:
- FACTURA_ELECTRONICA: el título dice "FACTURA ELECTRÓNICA".
- GUIA_DESPACHO: el título dice "GUÍA DE DESPACHO" (con o sin "ELECTRÓNICA") o solo "GUÍA ELECTRÓNICA". También suele ser un ticket térmico (por ejemplo de OXXO) con un recuadro "R.U.T. / GUIA ELECTRÓNICA / N°", montos NETO, EXENTO, IVA y TOTAL y un timbre electrónico del SII (código de barras) abajo.
- CONTROL_INTERNO: el título dice "CONTROL INTERNO". Suele ser un ticket de papel térmico angosto (por ejemplo de OXXO) con un recuadro que dice "R.U.T.", "CONTROL INTERNO" y "N°", y abajo NETO, EXENTO, IVA y TOTAL. Aunque parezca una boleta, si el recuadro dice CONTROL INTERNO es un CONTROL_INTERNO.
- DESCONOCIDO: todo lo demás: boletas, facturas exentas o no afectas, notas de crédito o débito, \
facturas de compra, liquidaciones, fotos, páginas en blanco, o documentos cuyo título no se ve o no se lee.

Reglas:
- evidence: copia literal del título que viste, tal cual aparece. Si no hay un título visible, null. \
Nunca inventes ni completes la evidencia.
- Si dudas del tipo, usa DESCONOCIDO: es preferible a equivocarse.
- Una página puede tener varios documentos (por ejemplo, dos facturas fotografiadas juntas): devuelve \
uno por documento, numerados de izquierda a derecha y de arriba abajo.
- Hoja adjunta que se IGNORA: una tira de papel angosta tipo ticket (impresa en impresora térmica), \
con un número arriba, una lista de productos con código, descripción y cantidad, y al final las líneas \
"Neto", "Iva", "Imp Adic." y "Total". Suele estar corcheteada o superpuesta sobre el documento real. \
Esa hoja NO tiene un recuadro con "R.U.T.", el tipo de documento y "N°". Un ticket térmico CON ese recuadro (por ejemplo un CONTROL INTERNO o una GUÍA ELECTRÓNICA de OXXO) es un documento real, nunca la hoja adjunta, aunque esté superpuesto sobre otro papel. \
No es un documento del lote: no la devuelvas como documento ni uses su número o su título. Si tapa parte \
de un documento, informa solo ese documento, con su zona completa. Solo si en la página no hay nada más \
que esa hoja, devuelve un único elemento DESCONOCIDO de página completa.
- Si la página no tiene ningún documento, devuelve un único elemento DESCONOCIDO de página completa.
- continuation_of_previous: true solo si el documento continúa el último documento de la página \
anterior (por ejemplo, la segunda hoja de la misma factura: sin título nuevo, el mismo número, o \
"página 2 de 3"). En la primera página del archivo siempre es false.
- document_number_seen: número o folio del documento como aparece (de "N° 001234" copia "001234"), o null.
- region: zona aproximada del documento en proporciones de la página (x, y: esquina superior \
izquierda; w, h: ancho y alto; todo entre 0 y 1). Si es el único documento de la página, usa x=0, y=0, w=1, h=1.
- confidence: de 0 a 1, tu seguridad en el tipo. Por debajo de 0.7 si el título está borroso, \
cortado o tapado.
- page_quality: ALTA, MEDIA o BAJA, y en issues los problemas visibles (borrosa, cortada, sombra, \
girada…), en español. Lista vacía si no hay."""


def model_name() -> str:
    return settings.SEGMENTER_MODEL or settings.AI_MODEL


def page_request(key: str, jpeg: bytes, page_number: int, total_pages: int, previous: str | None) -> client.AIRequest:
    """La solicitud al agente para una página. `previous` resume cómo terminó la página anterior."""
    context = (
        f"La página anterior terminaba con: {previous}."
        if previous
        else "Es la primera página del archivo: ningún documento puede ser continuación."
    )
    return client.AIRequest(
        key=key,
        kind="page_segmentation",
        system=SYSTEM_PROMPT,
        content=[client.text_part(f"Página {page_number} de {total_pages} del archivo. {context}"), client.image_part(jpeg)],
        schema=RESPONSE_SCHEMA,
        model=model_name(),
        parse=PageAnalysis.model_validate,
    )


def describe(doc_type: str, number: str | None) -> str:
    """Resumen de un documento para dar contexto al analizar la página siguiente."""
    number = re.sub(r"^\s*(N\s*[°ºo]\.?|FOLIO)\s*", "", number or "", flags=re.IGNORECASE).strip()
    return f"{doc_type}" + (f" N° {number}" if number else " (sin número visible)")


# --- Comprobaciones del código sobre la respuesta -------------------------------------------

# Títulos aceptados como evidencia de cada tipo (basta uno)
_REQUIRED = {
    "FACTURA_ELECTRONICA": ("FACTURA ELECTRONICA",),
    # La guía de despacho electrónica también se imprime solo como "GUÍA ELECTRÓNICA" (tickets OXXO)
    "GUIA_DESPACHO": ("GUIA DE DESPACHO", "GUIA ELECTRONICA"),
    "CONTROL_INTERNO": ("CONTROL INTERNO",),
}
# Documentos parecidos que no son del tipo admitido (factura exenta, liquidación-factura…)
_EXCLUDED = {"FACTURA_ELECTRONICA": ("EXENTA", "NO AFECTA", "LIQUIDACION", "NOTA DE CREDITO", "NOTA DE DEBITO")}


def normalize_text(text: str) -> str:
    """Mayúsculas, sin tildes y con espacios simples: 'Guía  de despacho' → 'GUIA DE DESPACHO'."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", plain).strip().upper()


def normalize_number(number: str | None) -> str | None:
    """Para comparar números de documento: solo dígitos y sin ceros iniciales ('N° 001234' → '1234')."""
    digits = re.sub(r"\D", "", number or "").lstrip("0")
    return digits or None


def verify_type(doc_type: str, evidence: str | None, confidence: float) -> tuple[str, list[dict]]:
    """Acepta el tipo propuesto solo con evidencia literal y confianza suficiente."""
    if doc_type == "DESCONOCIDO":
        return doc_type, []
    plain = normalize_text(evidence or "")
    matches = any(title in plain for title in _REQUIRED[doc_type])
    if not matches or any(word in plain for word in _EXCLUDED.get(doc_type, ())):
        return "DESCONOCIDO", [
            {
                "code": "CLASIFICACION_SIN_EVIDENCIA",
                "severity": "ADVERTENCIA",
                "message": f"La IA propuso {doc_type}, pero el título visto ({evidence or 'ninguno'}) no lo respalda.",
                "details": {"proposed": doc_type, "evidence": evidence},
            }
        ]
    if confidence < settings.CLASSIFICATION_MIN_CONFIDENCE:
        return "DESCONOCIDO", [
            {
                "code": "CLASIFICACION_DUDOSA",
                "severity": "ADVERTENCIA",
                "message": (
                    f"La IA propuso {doc_type} con confianza {confidence:.2f}, por debajo del mínimo "
                    f"{settings.CLASSIFICATION_MIN_CONFIDENCE:.2f}."
                ),
                "details": {"proposed": doc_type, "confidence": confidence},
            }
        ]
    return doc_type, []


def clean_region(region: Region, documents_on_page: int) -> tuple[dict | None, list[dict]]:
    """Zona del documento. Si es el único de la página, se usa la página completa (None)."""
    if documents_on_page == 1:
        return None, []
    inside = 0 <= region.x < 1 and 0 <= region.y < 1 and region.w > 0.02 and region.h > 0.02
    inside = inside and region.x + region.w <= 1.001 and region.y + region.h <= 1.001
    if not inside:
        return None, [
            {
                "code": "REGION_INVALIDA",
                "severity": "INFO",
                "message": "La zona del documento en la página no es válida; se usa la página completa.",
                "details": region.model_dump(),
            }
        ]
    return {"x": round(region.x, 4), "y": round(region.y, 4), "w": round(region.w, 4), "h": round(region.h, 4)}, []
