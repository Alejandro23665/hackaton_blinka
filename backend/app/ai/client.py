"""Cliente de Claude para los agentes: solicitudes con imagen(es) y respuesta JSON con esquema estricto.

- Las solicitudes se envían juntas en una tanda de la Message Batches API (mitad de precio; la
  mayoría termina en menos de una hora, máximo 24 h). Con AI_BATCH=false se llaman una por una
  con la Messages API (más rápido para probar).
- El esquema JSON lo hace cumplir el servidor (`output_config.format`): la respuesta siempre es
  JSON válido con esa forma. El código la vuelve a validar con `parse` (Pydantic).
- Caché en disco: una solicitud idéntica (mismas instrucciones, imágenes, esquema, modelo y lectura)
  devuelve la respuesta guardada sin volver a pagarla. Solo se guardan respuestas válidas.
- Errores: los que afectan a toda la tanda (clave, saldo, límite de uso) se lanzan como AIError;
  los de una solicitud se devuelven como AIError en el resultado de esa solicitud.
"""
import base64
import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

# Una tanda admite hasta 256 MB: se parte antes, con margen
MAX_BATCH_BYTES = 200 * 1024 * 1024
MAX_BATCH_REQUESTS = 100_000
# Palabras del esquema JSON que Claude no admite en output_config.format (el código las valida igual)
_UNSUPPORTED_SCHEMA_KEYS = {"minItems", "maxItems", "minimum", "maximum", "minLength", "maxLength", "multipleOf"}


class AIError(Exception):
    """Fallo de la IA. code: SIN_CLAVE, CLAVE (rechazada), CUOTA (saldo o límite de uso), PROVEEDOR,
    RECHAZO (Claude se negó) o FORMATO (respuesta incompleta o que no pasa la validación)."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass
class AIRequest:
    """Una solicitud al modelo. `key` la identifica dentro de la tanda (letras, números, - y _)."""

    key: str
    kind: str  # "page_segmentation" o "document_extraction"
    system: str
    content: list[dict]
    schema: dict
    model: str
    parse: Callable[[dict], Any]
    # Lecturas independientes del mismo contenido (1, 2…): la solicitud es la misma, la caché no
    reading: int = 1


@dataclass
class AIResult:
    data: dict[str, Any]
    # Lo que devolvió `parse` (por ejemplo, un modelo Pydantic ya validado)
    parsed: Any
    model: str
    cached: bool = False
    usage: dict[str, Any] = field(default_factory=dict)


def image_part(jpeg: bytes) -> dict:
    data = base64.standard_b64encode(jpeg).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}}


def text_part(text: str) -> dict:
    return {"type": "text", "text": text}


def claude_schema(schema: Any) -> Any:
    """El esquema de los agentes en la forma que admite Claude: `"type": [x, "null"]` pasa a `anyOf`
    y se quitan los límites numéricos y de largo (Pydantic los comprueba al validar)."""
    if isinstance(schema, list):
        return [claude_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    result = {key: claude_schema(value) for key, value in schema.items() if key not in _UNSUPPORTED_SCHEMA_KEYS}
    kind = result.get("type")
    if isinstance(kind, list):
        description = result.pop("description", None)
        del result["type"]
        result["anyOf"] = [{"type": t} for t in kind]
        if description:
            result["description"] = description
    return result


def _params(request: AIRequest) -> dict:
    return {
        "model": request.model,
        "max_tokens": settings.AI_MAX_TOKENS,
        "system": request.system,
        "messages": [{"role": "user", "content": request.content}],
        "output_config": {
            "effort": settings.AI_EFFORT,
            "format": {"type": "json_schema", "schema": claude_schema(request.schema)},
        },
    }


def _cache_path(request: AIRequest, params: dict):
    key = hashlib.sha256(
        json.dumps({"params": params, "reading": request.reading}, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return settings.AI_CACHE_DIR / key[:2] / f"{key}.json"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.CLAUDE_KEY, max_retries=settings.AI_MAX_RETRIES)


def _fatal(exc: anthropic.APIError) -> AIError:
    """Errores que impiden enviar la tanda: no tiene sentido seguir hasta corregirlos."""
    message = getattr(exc, "message", str(exc))
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return AIError(f"Claude rechazó la clave ({message}). Revisa CLAUDE_KEY en el .env.", "CLAVE")
    if isinstance(exc, anthropic.RateLimitError) or "credit balance" in message.lower():
        return AIError(f"Sin saldo o sobre el límite de uso de la API de Claude: {message}", "CUOTA")
    return AIError(f"Error de la API de Claude: {message}", "PROVEEDOR")


def _read_message(request: AIRequest, message) -> AIResult | AIError:
    """El JSON de la respuesta, validado. Un AIError si no sirve."""
    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None) if message.stop_details else None
        return AIError(f"Claude se negó a responder (categoría: {category}).", "RECHAZO")
    if message.stop_reason == "max_tokens":
        return AIError("La respuesta quedó cortada (AI_MAX_TOKENS es muy bajo).", "FORMATO")
    text = next((block.text for block in message.content if block.type == "text"), None)
    if text is None:
        return AIError("La respuesta no trae texto.", "FORMATO")
    try:
        data = json.loads(text)
        parsed = request.parse(data)
    except (ValueError, KeyError, TypeError) as exc:  # ValueError incluye los errores de Pydantic
        return AIError(f"La respuesta no tiene la forma esperada: {exc}", "FORMATO")
    usage = message.usage.model_dump() if message.usage else {}
    return AIResult(data=data, parsed=parsed, model=message.model, usage=usage)


def _run_direct(client: anthropic.Anthropic, pending: list[tuple[AIRequest, dict]], progress) -> dict:
    results = {}
    for number, (request, params) in enumerate(pending, start=1):
        progress(f"Consultando a Claude ({number} de {len(pending)})")
        try:
            message = client.messages.create(**params)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError, anthropic.RateLimitError) as exc:
            raise _fatal(exc) from exc
        except anthropic.APIStatusError as exc:
            if "credit balance" in exc.message.lower():
                raise _fatal(exc) from exc
            results[request.key] = AIError(f"Error de la API de Claude: {exc.message}", "PROVEEDOR")
            continue
        except anthropic.APIConnectionError as exc:
            results[request.key] = AIError(f"No se pudo contactar con Claude: {exc}", "PROVEEDOR")
            continue
        results[request.key] = _read_message(request, message)
    return results


def _chunks(pending: list[tuple[AIRequest, dict]]):
    """Parte las solicitudes en tandas dentro de los límites de la API."""
    chunk, size = [], 0
    for item in pending:
        item_size = len(json.dumps(item[1]))
        if chunk and (size + item_size > MAX_BATCH_BYTES or len(chunk) >= MAX_BATCH_REQUESTS):
            yield chunk
            chunk, size = [], 0
        chunk.append(item)
        size += item_size
    if chunk:
        yield chunk


def _run_batch(client: anthropic.Anthropic, pending: list[tuple[AIRequest, dict]], progress) -> dict:
    by_key = {request.key: request for request, _ in pending}
    results = {}
    for chunk in _chunks(pending):
        try:
            batch = client.messages.batches.create(
                requests=[{"custom_id": request.key, "params": params} for request, params in chunk]
            )
        except anthropic.APIError as exc:
            raise _fatal(exc) from exc
        logger.info("Tanda %s enviada con %d solicitudes", batch.id, len(chunk))
        deadline = time.monotonic() + settings.AI_BATCH_MAX_WAIT_S
        while batch.processing_status != "ended":
            counts = batch.request_counts
            done = counts.succeeded + counts.errored + counts.canceled + counts.expired
            progress(f"Esperando a Claude: tanda de {len(chunk)} solicitudes, {done} listas")
            if time.monotonic() > deadline:
                client.messages.batches.cancel(batch.id)
                raise AIError(f"La tanda {batch.id} no terminó a tiempo; se canceló.", "PROVEEDOR")
            time.sleep(settings.AI_BATCH_POLL_S)
            batch = client.messages.batches.retrieve(batch.id)
        # Los resultados llegan en cualquier orden: se emparejan por custom_id
        for item in client.messages.batches.results(batch.id):
            request = by_key[item.custom_id]
            outcome = item.result
            if outcome.type == "succeeded":
                results[request.key] = _read_message(request, outcome.message)
            elif outcome.type == "errored":
                error = outcome.error.error if hasattr(outcome.error, "error") else outcome.error
                results[request.key] = AIError(f"Claude no procesó la solicitud: {getattr(error, 'message', error)}", "PROVEEDOR")
            else:  # canceled o expired
                results[request.key] = AIError(f"La solicitud quedó {outcome.type} en la tanda.", "PROVEEDOR")
    return results


def run(requests: list[AIRequest], progress: Callable[[str], None] | None = None) -> dict[str, AIResult | AIError]:
    """Resuelve las solicitudes (caché o Claude). Devuelve, por `key`, el resultado o el AIError de
    esa solicitud. Lanza AIError si no se puede usar la API (sin clave, clave rechazada, sin saldo)."""
    progress = progress or (lambda _text: None)
    results: dict[str, AIResult | AIError] = {}
    pending: list[tuple[AIRequest, dict]] = []
    for request in requests:
        params = _params(request)
        cache_file = _cache_path(request, params)
        if settings.AI_CACHE_ENABLED and cache_file.is_file():
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            try:
                results[request.key] = AIResult(
                    data=cached["data"], parsed=request.parse(cached["data"]), model=cached["model"], cached=True
                )
                continue
            except (ValueError, KeyError, TypeError):
                pass  # la validación cambió y la respuesta guardada ya no sirve: se vuelve a pedir
        pending.append((request, params))
    if not pending:
        return results
    if not settings.CLAUDE_KEY:
        raise AIError("Falta CLAUDE_KEY en el archivo .env; los agentes no pueden leer documentos.", "SIN_CLAVE")

    client = _client()
    # Una respuesta incompleta o mal formada se vuelve a pedir (en una tanda nueva)
    for attempt in range(settings.AI_FORMAT_RETRIES + 1):
        answered = (_run_batch if settings.AI_BATCH else _run_direct)(client, pending, progress)
        retry = []
        for request, params in pending:
            outcome = answered[request.key]
            if isinstance(outcome, AIError) and outcome.code == "FORMATO" and attempt < settings.AI_FORMAT_RETRIES:
                retry.append((request, params))
                continue
            results[request.key] = outcome
            if isinstance(outcome, AIResult) and settings.AI_CACHE_ENABLED:
                cache_file = _cache_path(request, params)
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps({"model": outcome.model, "data": outcome.data}, ensure_ascii=False), encoding="utf-8")
        if not retry:
            break
        pending = retry
    return results
