"""Cliente de OpenRouter para los agentes: una llamada con imagen(es) y respuesta JSON con esquema estricto.

- Reintenta ante errores pasajeros (408, 429, 5xx) con espera creciente, y ante JSON inválido.
- El límite diario de los modelos gratuitos no se reintenta: se avisa con un error claro.
- Caché en disco: una llamada idéntica (mismos mensajes, esquema y modelo) devuelve la respuesta
  guardada sin gastar cuota. Cambiar la imagen, las instrucciones o el modelo cambia la clave.
"""
import base64
import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings


class AIError(Exception):
    """Fallo de la llamada a la IA. code: SIN_CLAVE, CLAVE (rechazada), CUOTA, PROVEEDOR o FORMATO."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


@dataclass
class AIResult:
    data: dict[str, Any]
    # Lo que devolvió `parse` (por ejemplo, un modelo Pydantic ya validado)
    parsed: Any
    model: str
    attempts: int
    duration_ms: int
    cost_usd: Decimal | None = None
    cached: bool = False
    usage: dict[str, Any] = field(default_factory=dict)


def image_part(jpeg: bytes) -> dict:
    encoded = base64.b64encode(jpeg).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}


def text_part(text: str) -> dict:
    return {"type": "text", "text": text}


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
        raise ValueError("el modelo no devolvió JSON")
    return json.loads(text[start : end + 1])


# Errores pasajeros del proveedor (saturación, límite por minuto, timeouts): vale la pena reintentar
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _is_daily_quota(status_code: int, body: dict) -> bool:
    """Límite diario de modelos gratuitos: no se arregla reintentando, solo al día siguiente o con créditos."""
    message = str((body.get("error") or {}).get("message", "")).lower()
    return status_code == 429 and ("per-day" in message or "per day" in message)


def _error(status_code: int, body: dict, raw_text: str) -> AIError:
    if _is_daily_quota(status_code, body):
        return AIError(
            "Se agotó el límite diario de uso gratuito de OpenRouter (se renueva a las 00:00 UTC). "
            "Reprocesa el lote después o añade créditos en openrouter.ai.",
            "CUOTA",
        )
    error = body.get("error") or {}
    message = error.get("message") or raw_text[:300] or "sin detalle"
    if status_code in (401, 403):
        return AIError(
            f"OpenRouter rechazó la clave ({status_code}: {message}). Revisa OPENROUTER_API_KEY en el .env: "
            "puede estar revocada o mal copiada.",
            "CLAVE",
        )
    provider = (error.get("metadata") or {}).get("provider_name")
    suffix = f" (proveedor {provider})" if provider else ""
    return AIError(f"OpenRouter respondió {status_code}: {message}{suffix}", "PROVEEDOR")


def _post_with_retries(payload: dict) -> tuple[dict, int]:
    """POST a OpenRouter con reintentos. Devuelve el cuerpo y el número de intentos."""
    headers = {"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}", "X-Title": "Captura de documentos"}
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
                raise AIError(f"No se pudo contactar con OpenRouter: {exc}", "PROVEEDOR") from exc
            time.sleep(2**attempt)
            continue

        is_json = response.headers.get("content-type", "").startswith("application/json")
        body = response.json() if is_json else {}
        error = body.get("error")
        if response.status_code == 200 and not error:
            return body, attempt + 1

        # OpenRouter puede devolver 200 con el error del proveedor dentro del cuerpo
        status_code = response.status_code
        if status_code == 200 and isinstance(error.get("code"), int):
            status_code = error["code"]
        if status_code in RETRYABLE_STATUS and not last and not _is_daily_quota(status_code, body):
            time.sleep(2**attempt)
            continue
        raise _error(status_code, body, response.text)
    raise AssertionError("inalcanzable")


def _cache_path(payload: dict):
    key = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return settings.AI_CACHE_DIR / key[:2] / f"{key}.json"


def call_json(
    *,
    system: str,
    content: list[dict],
    schema: dict,
    schema_name: str,
    model: str,
    parse: Callable[[dict], Any],
    temperature: float = 0,
) -> AIResult:
    """Llama al modelo y devuelve su JSON ya validado por `parse`.

    `parse` lanza ValueError (o un error de Pydantic, que lo es) si la respuesta no tiene la forma
    esperada: cuenta como respuesta mal formada, se vuelve a pedir y nunca se guarda en la caché.
    """
    if not settings.OPENROUTER_API_KEY:
        raise AIError("Falta OPENROUTER_API_KEY en el archivo .env; los agentes no pueden leer documentos.", "SIN_CLAVE")

    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
    }
    if settings.OPENROUTER_REASONING:
        # Forma parte de la llamada: cambiarlo cambia también la clave de la caché
        payload["reasoning"] = settings.OPENROUTER_REASONING
    cache_file = _cache_path(payload)
    if settings.AI_CACHE_ENABLED and cache_file.is_file():
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        try:
            return AIResult(
                data=cached["data"], parsed=parse(cached["data"]), model=cached["model"],
                attempts=0, duration_ms=0, cached=True,
            )
        except ValueError:
            pass  # la validación cambió y la respuesta guardada ya no sirve: se vuelve a pedir

    request = {**payload, "usage": {"include": True}}
    fallbacks = [m.strip() for m in settings.OPENROUTER_FALLBACK_MODELS.split(",") if m.strip()]
    if fallbacks:
        request["models"] = [model, *fallbacks]

    started = time.monotonic()
    total_attempts = 0
    # Una respuesta mal formada (sin JSON) suele ser pasajera: se vuelve a pedir
    format_attempts = max(1, settings.OPENROUTER_MAX_RETRIES + 1)
    for attempt in range(format_attempts):
        body, attempts = _post_with_retries(request)
        total_attempts += attempts
        try:
            data = _parse_json(_message_text(body["choices"][0]["message"]["content"]))
            if not isinstance(data, dict):
                raise ValueError("la respuesta no es un objeto JSON")
            parsed = parse(data)
            break
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            if attempt == format_attempts - 1:
                raise AIError(f"Respuesta del modelo con formato inválido tras {format_attempts} intentos: {exc}", "FORMATO") from exc

    usage = body.get("usage") or {}
    cost = usage.get("cost")
    result = AIResult(
        data=data,
        parsed=parsed,
        model=body.get("model", model),
        attempts=total_attempts,
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_usd=Decimal(str(cost)) if cost is not None else None,
        usage=usage,
    )
    if settings.AI_CACHE_ENABLED:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"model": result.model, "data": data}, ensure_ascii=False), encoding="utf-8")
    return result
