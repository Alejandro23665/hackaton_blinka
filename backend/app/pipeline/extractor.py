"""Agente B — Extractor (IA, una llamada por documento admitido).

Lee los 7 campos del documento y, para cada uno, dice si está LEIDO, AUSENTE o ILEGIBLE, el texto
tal como aparece y su confianza. No convierte ni calcula nada: convertir es trabajo del
normalizador y sumar, del validador.
"""
import io
from typing import Literal

from PIL import Image
from pydantic import BaseModel, Field, model_validator

from app.ai import client
from app.core.config import settings
from app.pipeline.fields import FIELD_NAMES

PROMPT_VERSION = "ext-13"
# Margen alrededor de la zona del documento al recortarla (proporción de la página)
CROP_MARGIN = 0.03


def _none_if_zero(value):
    """En el esquema, confidence y region_index no admiten null (Claude limita los campos que pueden
    ser null): 0 significa "no aplica" y se guarda como None."""
    return None if value == 0 else value


class FieldReading(BaseModel):
    status: Literal["LEIDO", "AUSENTE", "ILEGIBLE"]
    raw_text: str | None
    confidence: float | None = Field(default=None, ge=0, le=1)
    region_index: int | None

    @model_validator(mode="after")
    def _absent_values(self):
        self.region_index = _none_if_zero(self.region_index)
        if self.status == "AUSENTE":
            self.confidence = None
        return self


class SignatureReading(BaseModel):
    present: bool
    confidence: float | None = Field(default=None, ge=0, le=1)
    region_index: int | None
    description: str | None

    @model_validator(mode="after")
    def _absent_values(self):
        self.region_index = _none_if_zero(self.region_index)
        return self


# IVA y otros impuestos no los lee la IA como campos: el código los calcula con las líneas de impuesto
TAX_FIELDS = ("VAT_AMOUNT", "OTHER_TAXES_AMOUNT")
READ_FIELDS = tuple(name for name in FIELD_NAMES if name not in TAX_FIELDS)


class TaxLine(BaseModel):
    label: str
    status: Literal["LEIDO", "ILEGIBLE"]
    raw_text: str | None
    confidence: float | None = Field(default=None, ge=0, le=1)
    region_index: int | None

    @model_validator(mode="after")
    def _absent_values(self):
        self.region_index = _none_if_zero(self.region_index)
        return self


class Extraction(BaseModel):
    fields: dict[Literal[READ_FIELDS], FieldReading]  # type: ignore[valid-type]
    tax_lines: list[TaxLine]
    signature: SignatureReading
    transcription: str
    notes: str | None
    # Rótulo impreso junto a la fecha usada para ISSUE_DATE (el código rechaza "referencia", "vencimiento"…)
    date_label: str | None = None

    def model_post_init(self, __context) -> None:
        missing = set(READ_FIELDS) - set(self.fields)
        if missing:
            raise ValueError(f"faltan campos en la respuesta: {sorted(missing)}")


_FIELD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "raw_text", "confidence", "region_index"],
    "properties": {
        "status": {"type": "string", "enum": ["LEIDO", "AUSENTE", "ILEGIBLE"]},
        "raw_text": {"type": ["string", "null"], "description": "Texto exacto tal como aparece; usa ? en lo que no se lee"},
        "confidence": {"type": "number", "description": "Seguridad en la lectura, de 0 a 1; 0 si AUSENTE"},
        "region_index": {"type": "integer", "description": "Número de imagen donde está (1, 2…); 0 si AUSENTE"},
    },
}

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["fields", "tax_lines", "signature", "transcription", "notes", "date_label"],
    "properties": {
        "fields": {
            "type": "object",
            "additionalProperties": False,
            "required": list(READ_FIELDS),
            "properties": {name: _FIELD_SCHEMA for name in READ_FIELDS},
        },
        "tax_lines": {
            "type": "array",
            "description": "Cada línea de impuesto del documento (IVA, ILL, impuesto adicional…); vacía si no hay",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "status", "raw_text", "confidence", "region_index"],
                "properties": {
                    "label": {"type": "string", "description": "Nombre del impuesto tal como aparece, p. ej. \"IVA 19%\""},
                    "status": {"type": "string", "enum": ["LEIDO", "ILEGIBLE"]},
                    "raw_text": {"type": ["string", "null"], "description": "Monto exacto; usa ? en lo que no se lee"},
                    "confidence": {"type": "number", "description": "Seguridad, de 0 a 1"},
                    "region_index": {"type": "integer", "description": "Imagen donde está (1, 2…)"},
                },
            },
        },
        "signature": {
            "type": "object",
            "additionalProperties": False,
            "required": ["present", "confidence", "region_index", "description"],
            "properties": {
                "present": {"type": "boolean", "description": "true si hay una firma o anotación manuscrita"},
                "confidence": {"type": "number", "description": "Seguridad, de 0 a 1"},
                "region_index": {"type": "integer", "description": "Imagen donde está (1, 2…); 0 si no hay firma"},
                "description": {"type": ["string", "null"], "description": "Qué se ve, en una frase; null si no hay"},
            },
        },
        "transcription": {"type": "string", "description": "Todo el texto legible del documento, en orden de lectura"},
        "date_label": {"type": ["string", "null"], "description": "Rótulo impreso junto a la fecha de ISSUE_DATE; null si no tiene"},
        "notes": {"type": ["string", "null"], "description": "Problemas de lectura, en español; null si no hay"},
    },
}

SYSTEM_PROMPT = """Eres el extractor de un sistema de captura de documentos tributarios chilenos. \
Recibes las imágenes de UN documento (una por hoja o zona) y su tipo, y lees estos campos:

- PROVIDER_RUT: RUT de quien EMITE el documento (normalmente en el recuadro con el tipo y el número), \
no el del cliente o receptor.
- DOCUMENT_NUMBER: número o folio del documento (el "N°" del recuadro). En los tickets térmicos el \
cero se imprime con una barra (Ø): es 0, no 8 ni 9. Léelo dígito por dígito, sin completarlo.
- ISSUE_DATE: fecha de emisión: la que el documento rotula como tal ("Fecha", "Fecha Emisión", \
"FECHA :" en los tickets, o "Santiago, 18 de octubre de 2026" junto al encabezado). Nunca uses la \
fecha de referencia, de vencimiento, de la orden de compra ni la de una hoja adjunta: si la de emisión \
no se lee, es ILEGIBLE. En date_label copia el rótulo impreso junto a la fecha que usaste (por \
ejemplo "FECHA EMISION" o "FECHA :"), o null si no tiene rótulo.
- NET_AMOUNT: monto neto.
- EXEMPT_AMOUNT: monto exento.
- TOTAL_AMOUNT: monto total.

Y aparte, en tax_lines, CADA línea de impuesto por separado, con su nombre tal como aparece (label) y su monto (raw_text). Los impuestos posibles son: IVA (19 %), IABA 10%, IABA 18%, ILA VIN 20.5%, ILA CER 20.5%, ILA 31.5% (también impresos como ILL o "Imp. Adic."). Una entrada por línea; no las sumes ni incluyas neto, exento ni total. Si el monto de una línea está tapado (por ejemplo, por una perforación o un timbre) o no se lee, igualmente inclúyela con status ILEGIBLE y ? en lo que no se ve. Una línea de impuestos adicionales en 0 (por ejemplo "Impuestos: $0" o "Imp. Adic. 0") también se incluye, con 0. Si el documento no tiene ninguna línea de impuesto, tax_lines es una lista vacía.

Para cada campo devuelve:
- status: LEIDO si aparece y lo lees con seguridad; AUSENTE si no aparece en el documento; \
ILEGIBLE si aparece pero no se puede leer con seguridad (borroso, cortado, tapado por un timbre, sombra…).
- raw_text: el texto EXACTO como aparece, sin convertirlo (por ejemplo "$ 1.190.000", "14 de octubre \
de 2026", "76.123.456-0"). Si es ILEGIBLE, copia lo que sí ves y pon ? en cada carácter dudoso \
(por ejemplo "0?/03/2026"). Si es AUSENTE, null.
- confidence: de 0 a 1, tu seguridad en la lectura; 0 si AUSENTE.
- region_index: en qué imagen está (1 = la primera); 0 si AUSENTE.

Reglas:
- Nunca inventes, deduzcas ni calcules un valor: si el total no aparece, no lo calcules sumando; \
si falta el IVA, no lo calcules desde el neto. Lee solo lo que está escrito.
- Un monto que no aparece es AUSENTE, no 0. Usa 0 solo si el documento muestra 0 escrito.
- transcription: todo el texto legible del documento, en orden de lectura.
- Lee solo el documento del tipo indicado. Si en las imágenes aparece otro documento (por ejemplo un \
CONTROL INTERNO superpuesto sobre una GUÍA, o al revés), es otro documento: no uses sus datos; si \
tapa un dato del documento indicado, ese campo es ILEGIBLE.
- Ignora por completo la hoja adjunta tipo ticket si aparece: una tira de papel angosta (impresa en \
impresora térmica), con un número arriba, una lista de productos con código, descripción y cantidad, y \
al final las líneas "Neto", "Iva", "Imp Adic." y "Total". Suele estar corcheteada o superpuesta sobre el \
documento. Esa hoja NO tiene un recuadro con "R.U.T.", el tipo de documento y "N°". Un ticket térmico CON ese recuadro (por ejemplo un CONTROL INTERNO o una GUÍA ELECTRÓNICA de OXXO) es un documento real, nunca la hoja adjunta, aunque esté superpuesto sobre otro papel. Si el documento del tipo indicado es un ticket con ese recuadro, lo que se \
ve debajo de él no se lee. Suele titularse "Informe Ingreso". Una factura o guía en tira térmica larga puede quedar partida por esa hoja: la parte de arriba (con el recuadro R.U.T., tipo y N°) y la parte de abajo (detalle, Neto, Impuestos, IVA, Total y el total en palabras) son el MISMO documento y se leen las dos; lo único que se ignora es la tira de en medio. Nunca tomes de ella el número, el neto, el IVA, los impuestos adicionales ni el total: los \
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
    return settings.EXTRACTOR_MODEL or settings.AI_MODEL


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


def document_request(key: str, doc_type: str, images: list[tuple[bytes, str]], reading: int = 1) -> client.AIRequest:
    """La solicitud al agente para un documento. `images`: por cada región, en orden, la imagen y una
    descripción ("hoja 1 de 2…").

    `reading` distingue lecturas independientes del mismo documento (la segunda es la verificación):
    lo que se lee con nitidez sale igual; lo que el modelo adivina tiende a variar.
    """
    content = [
        client.text_part(
            f"{_TYPE_HINTS[doc_type]} El documento tiene {len(images)} imagen(es)."
        )
    ]
    for number, (jpeg, description) in enumerate(images, start=1):
        content.append(client.text_part(f"Imagen {number}: {description}"))
        content.append(client.image_part(jpeg))
    return client.AIRequest(
        key=key,
        kind="document_extraction",
        system=SYSTEM_PROMPT,
        content=content,
        schema=RESPONSE_SCHEMA,
        model=model_name(),
        parse=Extraction.model_validate,
        reading=reading,
    )
