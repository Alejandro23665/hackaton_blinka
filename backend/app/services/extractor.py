"""Extracción de datos de facturas con un modelo multimodal vía OpenRouter."""
import base64
import json
import re
import time
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

import httpx
from pydantic import BaseModel, Field, PlainSerializer, ValidationError

from app.core.config import settings


class ExtractionError(Exception):
    pass


# Importes como número en el JSON guardado (no como texto)
Amount = Annotated[Decimal | None, PlainSerializer(lambda v: None if v is None else float(v), when_used="json")]


class ExtractedInvoice(BaseModel):
    # Clasificación: ¿el archivo es una factura/boleta? Si no, el motivo en lenguaje natural
    is_invoice: bool = True
    not_invoice_reason: str | None = None
    vendor_name: str | None = None
    vendor_tax_id: str | None = None
    invoice_number: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    subtotal: Amount = None
    tax_amount: Amount = None
    total_amount: Amount = None
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


def _nullable(kind: str, description: str) -> dict:
    return {"type": [kind, "null"], "description": description}


# Esquema estricto: todas las claves son obligatorias; las desconocidas van en null
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_invoice", "not_invoice_reason", "vendor_name", "vendor_tax_id", "invoice_number", "issue_date", "due_date",
        "currency", "subtotal", "tax_amount", "total_amount", "confidence", "warnings",
    ],
    "properties": {
        "is_invoice": {"type": "boolean", "description": "true solo si el archivo es una factura, boleta o comprobante de pago"},
        "not_invoice_reason": _nullable("string", "Si is_invoice es false: qué es el archivo, en una frase en español"),
        "vendor_name": _nullable("string", "Razón social o nombre comercial del emisor"),
        "vendor_tax_id": _nullable("string", "Identificador fiscal del emisor (RUC, NIT, RFC, CUIT…), solo dígitos y letras"),
        "invoice_number": _nullable("string", "Número de factura o boleta tal como aparece, incluida la serie"),
        "issue_date": _nullable("string", "Fecha de emisión en formato YYYY-MM-DD"),
        "due_date": _nullable("string", "Fecha de vencimiento en formato YYYY-MM-DD; null si no aparece"),
        "currency": _nullable("string", "Código ISO 4217 de 3 letras"),
        "subtotal": _nullable("number", "Base imponible antes de impuestos"),
        "tax_amount": _nullable("number", "Total de impuestos (IVA/IGV…)"),
        "total_amount": _nullable("number", "Importe total a pagar, impuestos incluidos"),
        "confidence": {"type": "number", "description": "Confianza global de 0 a 1 en los datos extraídos"},
        "warnings": {"type": "array", "items": {"type": "string"}, "description": "Problemas encontrados, en español"},
    },
}

SYSTEM_PROMPT = """Eres el agente de cuentas por pagar de Blinka. Recibes una factura o boleta \
(PDF o foto) y extraes sus datos para decidir si se paga.

Reglas:
- Extrae solo lo que está en el documento. Si un dato no aparece o no se lee, usa null; nunca lo inventes.
- Importes como números con punto decimal y sin separadores de miles (1.234,50 → 1234.5).
- total_amount es el total a pagar con impuestos incluidos.
- Fechas en formato YYYY-MM-DD.
- currency en ISO 4217. Deduce la moneda por el símbolo y el país (S/ → PEN, € → EUR, US$ → USD). \
Si el símbolo es ambiguo (por ejemplo "$" sin país claro), elige la más probable y añade un aviso.
- vendor es quien EMITE la factura, no el cliente.
- confidence refleja qué tan seguro estás de los datos clave (proveedor, número, total, moneda). \
Baja de 0.8 si algo es dudoso, borroso o lo dedujiste.
- warnings: avisos breves en español (texto ilegible, totales que no cuadran, moneda deducida, \
falta fecha de vencimiento…). Lista vacía si todo es claro.
- Primero decide si el archivo es una factura, boleta o comprobante de pago (is_invoice). Si no lo es (foto, captura, documento de otro tipo, ilustración…), devuelve is_invoice false, describe brevemente qué es en not_invoice_reason, deja los demás datos en null y confidence 0.
- Si es una factura pero ilegible o incompleta, is_invoice es true y los datos que falten van en null."""


def _file_part(data: bytes, content_type: str, filename: str) -> dict:
    encoded = base64.b64encode(data).decode()
    data_url = f"data:{content_type};base64,{encoded}"
    if content_type == "application/pdf":
        return {"type": "file", "file": {"filename": filename, "file_data": data_url}}
    return {"type": "image_url", "image_url": {"url": data_url}}


def _message_text(content: Any) -> str:
    if isinstance(content, list):  # algunos proveedores devuelven partes
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def _parse_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ExtractionError("El modelo no devolvió JSON")
    return json.loads(text[start : end + 1])


# Errores pasajeros del proveedor (saturación, límite de uso, timeouts): vale la pena reintentar
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _error_message(status_code: int, body: dict, raw_text: str) -> str:
    error = body.get("error") or {}
    message = error.get("message") or raw_text[:300] or "sin detalle"
    metadata = error.get("metadata") or {}
    provider = metadata.get("provider_name")
    detail = metadata.get("raw")
    if detail and not isinstance(detail, str):
        detail = json.dumps(detail, ensure_ascii=False)
    parts = [f"OpenRouter respondió {status_code}: {message}"]
    if provider:
        parts.append(f"proveedor {provider}")
    if detail:
        parts.append(str(detail)[:200])
    if status_code in RETRYABLE_STATUS:
        parts.append("suele ser temporal; vuelve a subir el archivo en unos segundos")
    return " · ".join(parts)


def _post_with_retries(payload: dict, headers: dict) -> dict:
    """POST a OpenRouter con reintentos y espera creciente ante errores pasajeros."""
    attempts = max(1, settings.OPENROUTER_MAX_RETRIES + 1)
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            response = httpx.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=settings.OPENROUTER_TIMEOUT_S,
            )
        except httpx.HTTPError as exc:
            if last:
                raise ExtractionError(f"No se pudo contactar con OpenRouter: {exc}") from exc
            time.sleep(2**attempt)
            continue

        is_json = response.headers.get("content-type", "").startswith("application/json")
        body = response.json() if is_json else {}
        error = body.get("error")
        if response.status_code == 200 and not error:
            return body

        # OpenRouter puede devolver 200 con el error del proveedor dentro del cuerpo
        status_code = response.status_code
        if status_code == 200 and isinstance(error.get("code"), int):
            status_code = error["code"]
        if status_code in RETRYABLE_STATUS and not last:
            time.sleep(2**attempt)
            continue
        raise ExtractionError(_error_message(status_code, body, response.text))
    raise AssertionError("inalcanzable")


def extract_invoice(data: bytes, content_type: str, filename: str) -> tuple[ExtractedInvoice, dict]:
    """Devuelve los datos extraídos y metadatos (modelo, tokens)."""
    if not settings.OPENROUTER_API_KEY:
        raise ExtractionError("Falta OPENROUTER_API_KEY en el archivo .env; el agente no puede leer facturas.")

    payload = {
        "model": settings.OPENROUTER_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Extrae los datos de esta factura ({filename})."},
                    _file_part(data, content_type, filename),
                ],
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "invoice_extraction", "strict": True, "schema": RESPONSE_SCHEMA},
        },
    }
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "X-Title": "Blinka",
    }

    fallbacks = [m.strip() for m in settings.OPENROUTER_FALLBACK_MODELS.split(",") if m.strip()]
    if fallbacks:
        # OpenRouter prueba estos modelos en orden si el principal falla
        payload["models"] = [settings.OPENROUTER_MODEL, *fallbacks]

    # Una respuesta mal formada (sin JSON, campos inválidos) suele ser pasajera: se vuelve a pedir
    attempts = max(1, settings.OPENROUTER_MAX_RETRIES + 1)
    for attempt in range(attempts):
        body = _post_with_retries(payload, headers)
        try:
            text = _message_text(body["choices"][0]["message"]["content"])
            extracted = ExtractedInvoice.model_validate(_parse_json(text))
            break
        except (KeyError, IndexError, json.JSONDecodeError, ValidationError, ExtractionError) as exc:
            if attempt == attempts - 1:
                raise ExtractionError(
                    f"Respuesta del modelo con formato inválido tras {attempts} intentos: {exc}"
                ) from exc

    meta = {"model": body.get("model", settings.OPENROUTER_MODEL), "usage": body.get("usage")}
    return extracted, meta
