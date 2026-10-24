"""Agente B — Extractor (IA, una llamada por documento admitido).

Lee los 7 campos del documento y, para cada uno, dice si está LEIDO, AUSENTE o ILEGIBLE, el texto
tal como aparece y su confianza. No convierte ni calcula nada: convertir es trabajo del
normalizador y sumar, del validador.
"""
import io
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field

from app.ai import client
from app.core.config import settings
from app.models.enums import FIELD_NAMES

PROMPT_VERSION = "ext-5"
# Margen alrededor de la zona del documento al recortarla (proporción de la página)
CROP_MARGIN = 0.03


class FieldReading(BaseModel):
    status: Literal["LEIDO", "AUSENTE", "ILEGIBLE"]
    raw_text: str | None
    confidence: float | None = Field(default=None, ge=0, le=1)
    region_index: int | None


class SignatureReading(BaseModel):
    present: bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    region_index: int | None
    description: str | None


class Extraction(BaseModel):
    fields: dict[Literal[FIELD_NAMES], FieldReading]  # type: ignore[valid-type]
    signature: SignatureReading
    transcription: str
    notes: str | None

    def model_post_init(self, __context) -> None:
        missing = set(FIELD_NAMES) - set(self.fields)
        if missing:
            raise ValueError(f"faltan campos en la respuesta: {sorted(missing)}")


_FIELD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "raw_text", "confidence", "region_index"],
    "properties": {
        "status": {"type": "string", "enum": ["LEIDO", "AUSENTE", "ILEGIBLE"]},
        "raw_text": {"type": ["string", "null"], "description": "Texto exacto tal como aparece; usa ? en lo que no se lee"},
        "confidence": {"type": ["number", "null"], "description": "Seguridad en la lectura, de 0 a 1; null si AUSENTE"},
        "region_index": {"type": ["integer", "null"], "description": "Número de imagen donde está (1, 2…); null si AUSENTE"},
    },
}

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fields", "signature", "transcription", "notes"],
    "properties": {
        "fields": {
            "type": "object",
            "additionalProperties": False,
            "required": list(FIELD_NAMES),
            "properties": {name: _FIELD_SCHEMA for name in FIELD_NAMES},
        },
        "signature": {
            "type": "object",
            "additionalProperties": False,
            "required": ["present", "confidence", "region_index", "description"],
            "properties": {
                "present": {"type": "boolean", "description": "true si hay una firma o anotación manuscrita"},
                "confidence": {"type": ["number", "null"], "description": "Seguridad, de 0 a 1"},
                "region_index": {"type": ["integer", "null"], "description": "Imagen donde está; null si no hay"},
                "description": {"type": ["string", "null"], "description": "Qué se ve, en una frase; null si no hay"},
            },
        },
        "transcription": {"type": "string", "description": "Todo el texto legible del documento, en orden de lectura"},
        "notes": {"type": ["string", "null"], "description": "Problemas de lectura, en español; null si no hay"},
    },
}

SYSTEM_PROMPT = """Eres el extractor de un sistema de captura de documentos tributarios chilenos. \
Recibes las imágenes de UN documento (una por hoja o zona) y su tipo, y lees estos campos:

- PROVIDER_RUT: RUT de quien EMITE el documento (normalmente en el recuadro con el tipo y el número), \
no el del cliente o receptor.
- DOCUMENT_NUMBER: número o folio del documento (el "N°" del recuadro).
- ISSUE_DATE: fecha de emisión.
- NET_AMOUNT: monto neto.
- TAX_AMOUNT: impuestos (IVA y otros impuestos, si los hay).
- EXEMPT_AMOUNT: monto exento.
- TOTAL_AMOUNT: monto total.

Para cada campo devuelve:
- status: LEIDO si aparece y lo lees con seguridad; AUSENTE si no aparece en el documento; \
ILEGIBLE si aparece pero no se puede leer con seguridad (borroso, cortado, tapado por un timbre, sombra…).
- raw_text: el texto EXACTO como aparece, sin convertirlo (por ejemplo "$ 1.190.000", "14 de octubre \
de 2026", "76.123.456-0"). Si es ILEGIBLE, copia lo que sí ves y pon ? en cada carácter dudoso \
(por ejemplo "0?/03/2026"). Si es AUSENTE, null.
- confidence: de 0 a 1, tu seguridad en la lectura; null si AUSENTE.
- region_index: en qué imagen está (1 = la primera); null si AUSENTE.

Reglas:
- Nunca inventes, deduzcas ni calcules un valor: si el total no aparece, no lo calcules sumando; \
si falta el IVA, no lo calcules desde el neto. Lee solo lo que está escrito.
- Un monto que no aparece es AUSENTE, no 0. Usa 0 solo si el documento muestra 0 escrito.
- transcription: todo el texto legible del documento, en orden de lectura.
- Ignora por completo la hoja adjunta tipo ticket si aparece: una tira de papel angosta (impresa en \
impresora térmica), con un número arriba, una lista de productos con código, descripción y cantidad, y \
al final las líneas "Neto", "Iva", "Imp Adic." y "Total". Suele estar corcheteada o superpuesta sobre el \
documento. Nunca tomes de ella el número, el neto, el IVA, los impuestos adicionales ni el total: los \
campos se leen solo del documento, y su texto no va en transcription. Si esa hoja tapa un dato del \
documento, ese campo es ILEGIBLE.
- signature: si el documento está FIRMADO. present es true si hay trazos manuscritos de recepción: una firma o rúbrica, o un nombre, RUT o fecha escritos a mano (normalmente con lápiz azul o negro, en la parte inferior, sobre o junto a un recuadro con "Nombre:", "RUT:", "Fecha:", "Recinto:" o "Firma:"). Un recuadro con esas etiquetas pero vacío, o solo texto impreso, es false. La firma puede estar en cualquier hoja: indica en region_index en cuál.
- Lo escrito a mano en ese recuadro NO es un dato del documento: nunca uses ese RUT, nombre o fecha manuscritos para PROVIDER_RUT ni ISSUE_DATE.
- notes: problemas de lectura en una frase, en español, o null."""

_TYPE_HINTS = {
    "FACTURA_ELECTRONICA": "Es una FACTURA ELECTRÓNICA: normalmente tiene monto neto, IVA y total; "
    "el monto exento solo aparece en facturas con ítems exentos.",
    "GUIA_DESPACHO": "Es una GUÍA DE DESPACHO (también titulada GUÍA ELECTRÓNICA): puede no tener montos "
    "(traslado sin valorizar); si no hay ninguna sección de montos, marca los cuatro montos como AUSENTE. "
    "A menudo es un ticket térmico (por ejemplo de OXXO): RUT y número en el recuadro superior, \"FECHA :\" "
    "y montos NETO, EXENTO, IVA 19% y TOTAL. Un EXENTO que muestra 0 es 0 (LEIDO). El RUT del emisor es el "
    "del recuadro, no el del receptor (\"Srs:\") ni los campos vacíos del pie.",
    "CONTROL_INTERNO": "Es un CONTROL INTERNO, a menudo un ticket térmico (por ejemplo de OXXO): el RUT y el "
    "número están en el recuadro superior (R.U.T. y N°); la fecha suele estar como \"FECHA :\" y los montos "
    "abajo como NETO, EXENTO, IVA 19% y TOTAL. Un EXENTO que muestra 0 es 0 (LEIDO), no ausente. No confundas "
    "el RUT del recuadro con campos vacíos del pie (Nombre, RUT, Fecha, Firma).",
}


def model_name() -> str:
    return settings.EXTRACTOR_MODEL or settings.OPENROUTER_MODEL


def crop(jpeg: bytes, bbox: dict) -> bytes:
    """Recorta la zona del documento (con margen) de la imagen de la página."""
    with Image.open(io.BytesIO(jpeg)) as image:
        width, height = image.size
        left = max(0.0, bbox["x"] - CROP_MARGIN) * width
        top = max(0.0, bbox["y"] - CROP_MARGIN) * height
        right = min(1.0, bbox["x"] + bbox["w"] + CROP_MARGIN) * width
        bottom = min(1.0, bbox["y"] + bbox["h"] + CROP_MARGIN) * height
        piece = image.crop((int(left), int(top), int(right), int(bottom)))
        buffer = io.BytesIO()
        piece.convert("RGB").save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()


def extract_document(doc_type: str, images: list[tuple[bytes, str]], temperature: float = 0) -> client.AIResult:
    """`images`: por cada región del documento, en orden, la imagen y una descripción ("hoja 1 de 2…").

    `temperature` > 0 se usa en la segunda lectura (verificación): lo que se lee con nitidez sale igual;
    lo que el modelo adivina tiende a variar.
    """
    content = [
        client.text_part(
            f"{_TYPE_HINTS[doc_type]} El documento tiene {len(images)} imagen(es)."
        )
    ]
    for number, (jpeg, description) in enumerate(images, start=1):
        content.append(client.text_part(f"Imagen {number}: {description}"))
        content.append(client.image_part(jpeg))
    return client.call_json(
        system=SYSTEM_PROMPT,
        content=content,
        schema=RESPONSE_SCHEMA,
        schema_name="document_extraction",
        model=model_name(),
        parse=Extraction.model_validate,
        temperature=temperature,
    )
