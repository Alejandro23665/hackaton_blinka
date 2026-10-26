"""Cliente de Claude: tandas, caché, reintentos y errores, con un SDK de Anthropic simulado (sin red)."""
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.ai import client as ai
from app.core.config import settings

# El cliente real, guardado antes de que el FakeAI de conftest lo sustituya en cada test
REAL_RUN = ai.run


def _message(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=text)],
        model="claude-haiku-5-5",
        usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 2000, "output_tokens": 1000}),
    )


class FakeSDK:
    """Lo mínimo del SDK que usa el cliente. `answers`: por custom_id, una lista de respuestas
    (mensajes o resultados de error) que se van entregando en orden."""

    def __init__(self):
        self.answers: dict[str, list] = {}
        self.batches: list[list[dict]] = []
        self.created: list[dict] = []
        self.batch_error: Exception | None = None
        self.messages = SimpleNamespace(
            create=self._create,
            batches=SimpleNamespace(create=self._batch, retrieve=self._retrieve, results=self._results, cancel=lambda _id: None),
        )

    def _next(self, key):
        return self.answers[key].pop(0)

    def _create(self, **params):
        self.created.append(params)
        return self._next(params["messages"][0]["content"][0]["text"])

    def _batch(self, requests):
        if self.batch_error:
            raise self.batch_error
        self.batches.append(requests)
        counts = SimpleNamespace(succeeded=0, errored=0, canceled=0, expired=0, processing=len(requests))
        return SimpleNamespace(id=f"lote{len(self.batches)}", processing_status="in_progress", request_counts=counts)

    def _retrieve(self, batch_id):
        return SimpleNamespace(id=batch_id, processing_status="ended")

    def _results(self, batch_id):
        requests = self.batches[int(batch_id.removeprefix("lote")) - 1]
        items = []
        for request in reversed(requests):  # en cualquier orden: el cliente empareja por custom_id
            answer = self._next(request["custom_id"])
            if isinstance(answer, str):
                result = SimpleNamespace(type="errored", error=SimpleNamespace(error=SimpleNamespace(message=answer)))
            else:
                result = SimpleNamespace(type="succeeded", message=answer)
            items.append(SimpleNamespace(custom_id=request["custom_id"], result=result))
        return items


@pytest.fixture
def sdk(monkeypatch):
    fake = FakeSDK()
    monkeypatch.setattr(ai, "run", REAL_RUN)
    monkeypatch.setattr(ai, "_client", lambda: fake)
    monkeypatch.setattr(ai.time, "sleep", lambda _: None)
    monkeypatch.setattr(settings, "AI_BATCH", True)
    return fake


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["v", "nota"],
    "properties": {"v": {"type": "integer"}, "nota": {"type": ["string", "null"], "description": "opcional"}},
}


def _request(key, reading=1, text=None):
    return ai.AIRequest(
        key=key, kind="x", system="s", content=[ai.text_part(text or key)], schema=SCHEMA,
        model="claude-haiku-5-5", parse=lambda d: d["v"], reading=reading,
    )


def test_requests_go_in_one_batch_and_results_are_matched_by_id(sdk):
    sdk.answers = {"a": [_message('{"v": 1, "nota": null}')], "b": [_message('{"v": 2, "nota": "x"}')]}
    results = ai.run([_request("a"), _request("b")])
    assert {key: r.parsed for key, r in results.items()} == {"a": 1, "b": 2}
    (batch,) = sdk.batches
    params = batch[0]["params"]
    assert [r["custom_id"] for r in batch] == ["a", "b"]
    assert params["model"] == "claude-haiku-5-5" and "temperature" not in params
    assert params["output_config"]["effort"] == settings.AI_EFFORT
    # Claude no admite "type": [x, "null"]: se envía como anyOf
    nota = params["output_config"]["format"]["schema"]["properties"]["nota"]
    assert nota == {"anyOf": [{"type": "string"}, {"type": "null"}], "description": "opcional"}


def test_identical_request_uses_cache_but_another_reading_does_not(sdk):
    sdk.answers = {"a": [_message('{"v": 1, "nota": null}'), _message('{"v": 5, "nota": null}')]}
    ai.run([_request("a")])
    again = ai.run([_request("a")])["a"]
    assert (again.parsed, again.cached, len(sdk.batches)) == (1, True, 1)
    # La segunda lectura del mismo documento es otra solicitud (no reutiliza la primera)
    assert ai.run([_request("a", reading=2)])["a"].parsed == 5 and len(sdk.batches) == 2


def test_invalid_answer_is_asked_again_and_never_cached(sdk):
    sdk.answers = {"a": [_message('{"otro": 1}'), _message('{"v": 3, "nota": null}')], "b": [_message('{"v": 4, "nota": null}')]}
    results = ai.run([_request("a"), _request("b")])
    assert (results["a"].parsed, results["b"].parsed) == (3, 4)
    assert [[r["custom_id"] for r in batch] for batch in sdk.batches] == [["a", "b"], ["a"]]


def test_refusal_truncation_and_request_errors_are_per_request(sdk, monkeypatch):
    monkeypatch.setattr(settings, "AI_FORMAT_RETRIES", 0)
    sdk.answers = {
        "a": [_message("", stop_reason="refusal")],
        "b": [_message('{"v": 1', stop_reason="max_tokens")],
        "c": ["overloaded"],
        "d": [_message('{"v": 7, "nota": null}')],
    }
    results = ai.run([_request(k) for k in "abcd"])
    assert [results[k].code for k in "abc"] == ["RECHAZO", "FORMATO", "PROVEEDOR"]
    assert results["d"].parsed == 7


def test_direct_mode_calls_the_messages_api(sdk, monkeypatch):
    monkeypatch.setattr(settings, "AI_BATCH", False)
    sdk.answers = {"a": [_message('{"v": 1, "nota": null}')]}
    assert ai.run([_request("a")])["a"].parsed == 1
    assert len(sdk.created) == 1 and sdk.batches == []


def test_missing_key_only_matters_when_something_must_be_asked(sdk, monkeypatch):
    sdk.answers = {"a": [_message('{"v": 1, "nota": null}')]}
    ai.run([_request("a")])
    monkeypatch.setattr(settings, "CLAUDE_KEY", None)
    assert ai.run([_request("a")])["a"].cached  # desde la caché, sin clave
    with pytest.raises(ai.AIError) as exc:
        ai.run([_request("nuevo")])
    assert exc.value.code == "SIN_CLAVE" and "CLAUDE_KEY" in str(exc.value)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (anthropic.AuthenticationError, "CLAVE"),
        (anthropic.RateLimitError, "CUOTA"),
        (anthropic.InternalServerError, "PROVEEDOR"),
    ],
)
def test_batch_that_cannot_be_sent_stops_everything(sdk, error, code):
    status = {"CLAVE": 401, "CUOTA": 429, "PROVEEDOR": 500}[code]
    response = httpx2.Response(status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages/batches"))
    sdk.batch_error = error("falló", response=response, body=None)
    with pytest.raises(ai.AIError) as exc:
        ai.run([_request("a")])
    assert exc.value.code == code


def test_schema_conversion_drops_unsupported_constraints():
    schema = {"type": "array", "minItems": 1, "items": {"type": "number", "minimum": 0, "maximum": 1}}
    assert ai.claude_schema(schema) == {"type": "array", "items": {"type": "number"}}
    assert json.dumps(ai.claude_schema(SCHEMA))  # sigue siendo JSON serializable


def test_each_paid_attempt_is_reported_with_tokens_cost_and_batch(sdk):
    sdk.answers = {"a": [_message('{"otro": 1}'), _message('{"v": 3, "nota": null}')]}
    calls = ai.run([_request("a")])["a"].calls
    # La respuesta inválida también se pagó: cuenta como un intento FORMATO
    assert [(c.batch_id, c.input_tokens, c.output_tokens, c.outcome) for c in calls] == [
        ("lote1", 2000, 1000, "FORMATO"), ("lote2", 2000, 1000, "OK"),
    ]
    assert str(calls[0].cost_usd) == "0.000350"  # (2.000 × 0,10 + 1.000 × 0,50) / 1M, a mitad de precio
    assert ai.run([_request("a")])["a"].calls == []  # desde la caché: no se paga
