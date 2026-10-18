"""Subida de facturas. El extractor (OpenRouter) se sustituye por uno falso: no hay llamadas de red."""
from decimal import Decimal

import pytest

from app.core.config import settings
from app.services import extractor
from app.services.extractor import ExtractedInvoice, ExtractionError

PDF = b"%PDF-1.4\n% factura de prueba\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

POLICY = {
    "name": "Base",
    "max_amount_per_invoice": 5000,
    "period_budget": 20000,
    "require_human_above": 1000,
    "allowed_currencies": ["PEN", "USD"],
}


def fake_extraction(**overrides) -> ExtractedInvoice:
    data = dict(
        vendor_name="ACME Suministros",
        vendor_tax_id="20-123456789",
        invoice_number="F001-000123",
        issue_date="2026-10-01",
        due_date="2026-10-31",
        currency="PEN",
        subtotal=Decimal("400"),
        tax_amount=Decimal("72"),
        total_amount=Decimal("472"),
        confidence=0.96,
        warnings=[],
    )
    return ExtractedInvoice(**{**data, **overrides})


@pytest.fixture
def storage_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "STORAGE_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def extract(monkeypatch):
    """Permite fijar qué devuelve el extractor en cada test."""
    state = {"result": fake_extraction(), "calls": 0}

    def fake(data, content_type, filename):
        state["calls"] += 1
        if isinstance(state["result"], Exception):
            raise state["result"]
        return state["result"], {"model": "test/model", "usage": None}

    monkeypatch.setattr(extractor, "extract_invoice", fake)
    return state


def upload(client, content=PDF, name="factura.pdf"):
    return client.post("/documents", files={"file": (name, content, "application/octet-stream")})


def test_upload_known_vendor_creates_and_approves_invoice(client, storage_dir, extract):
    client.put("/exchange-rates/PEN", json={"usd_per_unit": 0.27})  # 472 PEN = 127,44 USD
    client.post("/policies", json=POLICY)
    client.post("/vendors", json={"name": "acme suministros"})  # coincide por nombre

    response = upload(client)
    assert response.status_code == 201, response.text
    doc = response.json()
    assert doc["status"] == "processed"
    assert doc["content_type"] == "application/pdf"
    assert doc["extraction"]["data"]["total_amount"] == 472.0

    # El archivo quedó guardado en local y se puede descargar
    assert len(list(storage_dir.rglob("*.pdf"))) == 1
    file_response = client.get(f"/documents/{doc['id']}/file")
    assert file_response.status_code == 200
    assert file_response.content == PDF

    invoice = client.get(f"/invoices/{doc['invoice_id']}").json()
    assert invoice["status"] == "approved"
    assert invoice["amount"] == 472.0
    assert invoice["currency"] == "PEN"
    assert invoice["document"]["id"] == doc["id"]
    assert invoice["vendor"]["tax_id"] == "20123456789"  # normalizado y guardado
    rules = {r["rule"]: r for r in invoice["decisions"][0]["rules_evaluated"]}
    assert rules["document_extraction"]["passed"] is True
    assert "472,00 PEN = 127,44 USD" in rules["currency_conversion"]["detail"]


def test_unknown_vendor_is_created_pending_and_invoice_escalated(client, storage_dir, extract):
    client.post("/policies", json=POLICY)
    extract["result"] = fake_extraction(vendor_name="Nuevo Proveedor SAC", vendor_tax_id="20999")

    doc = upload(client).json()
    invoice = client.get(f"/invoices/{doc['invoice_id']}").json()
    assert invoice["status"] == "escalated"
    assert invoice["vendor"]["needs_review"] is True
    assert invoice["vendor"]["is_allowed"] is False
    assert doc["extraction"]["vendor_created"] is True

    # Al aprobar al proveedor deja de estar pendiente
    vendor = client.patch(f"/vendors/{invoice['vendor']['id']}", json={"is_allowed": True}).json()
    assert vendor["needs_review"] is False


def test_missing_due_date_uses_issue_date_and_escalates(client, storage_dir, extract):
    client.post("/policies", json=POLICY)
    client.post("/vendors", json={"name": "ACME Suministros"})
    extract["result"] = fake_extraction(due_date=None, confidence=0.95)

    doc = upload(client, PNG, "foto.png").json()
    assert doc["content_type"] == "image/png"
    assert any("vencimiento" in w for w in doc["extraction"]["warnings"])
    invoice = client.get(f"/invoices/{doc['invoice_id']}").json()
    assert invoice["due_date"] == "2026-10-01"  # fecha de emisión
    assert invoice["status"] == "escalated"


def test_extraction_error_keeps_document_as_failed(client, storage_dir, extract):
    extract["result"] = ExtractionError("Falta OPENROUTER_API_KEY")
    doc = upload(client).json()
    assert doc["status"] == "failed"
    assert "OPENROUTER_API_KEY" in doc["error"]
    assert doc["invoice_id"] is None
    assert client.get("/documents").json()[0]["id"] == doc["id"]


def test_failed_document_can_be_retried_with_same_file(client, storage_dir, extract):
    client.post("/policies", json=POLICY)
    extract["result"] = ExtractionError("Falta OPENROUTER_API_KEY")
    failed = upload(client).json()
    assert failed["status"] == "failed"

    extract["result"] = fake_extraction()
    response = upload(client)
    assert response.status_code == 201
    retried = response.json()
    assert retried["id"] == failed["id"]
    assert retried["status"] == "processed"
    assert retried["error"] is None
    assert len(client.get("/documents").json()) == 1
    assert len(list(storage_dir.rglob("*.pdf"))) == 1


def test_non_invoice_file_is_reported_as_such(client, storage_dir, extract):
    extract["result"] = ExtractedInvoice(
        is_invoice=False,
        not_invoice_reason="Es una ilustración de cuatro personajes de bloques.",
        confidence=0,
        warnings=[],
    )
    doc = upload(client, PNG, "ideas.png").json()
    assert doc["status"] == "failed"
    assert doc["error"] == "El archivo no es una factura ni una boleta: Es una ilustración de cuatro personajes de bloques."
    assert client.get("/invoices").json() == []


def test_non_invoice_detected_even_if_model_skips_the_flag(client, storage_dir, extract):
    # Modelo que no rellena is_invoice pero no encontró nada y lo explica en los avisos
    extract["result"] = ExtractedInvoice(confidence=0, warnings=["El archivo es una captura de un chat."])
    doc = upload(client, PNG, "chat.png").json()
    assert doc["error"] == "El archivo no es una factura ni una boleta: El archivo es una captura de un chat."


def test_missing_key_fields_fail_without_creating_invoice(client, storage_dir, extract):
    extract["result"] = fake_extraction(total_amount=None, invoice_number=None)
    doc = upload(client).json()
    assert doc["status"] == "failed"
    assert "número de factura" in doc["error"] and "monto total" in doc["error"]
    assert client.get("/invoices").json() == []


def test_duplicates(client, storage_dir, extract):
    client.post("/policies", json=POLICY)
    first = upload(client).json()
    # Mismo archivo -> 409 y no se vuelve a llamar al modelo
    assert upload(client).status_code == 409
    assert extract["calls"] == 1

    # Otro archivo con la misma factura -> se lee, se registra y el agente la bloquea
    doc = upload(client, PDF + b"%copia", "copia.pdf").json()
    assert doc["status"] == "processed"
    invoice = client.get(f"/invoices/{doc['invoice_id']}").json()
    assert invoice["status"] == "blocked"
    assert invoice["document"]["original_name"] == "copia.pdf"
    rule = next(r for r in invoice["decisions"][0]["rules_evaluated"] if r["rule"] == "duplicate_invoice")
    assert rule["passed"] is False
    assert f"id {first['invoice_id']}" in rule["detail"]

    # La original no cambia al reevaluarla: el duplicado es siempre la posterior
    original = client.post(f"/invoices/{first['invoice_id']}/evaluate").json()
    dup_rule = next(r for r in original["decisions"][-1]["rules_evaluated"] if r["rule"] == "duplicate_invoice")
    assert dup_rule["passed"] is True


def test_rejects_unsupported_and_empty_files(client, storage_dir, extract):
    assert upload(client, b"hola", "nota.txt").status_code == 415
    assert upload(client, b"", "vacio.pdf").status_code == 422
    assert extract["calls"] == 0


# --- Llamada HTTP a OpenRouter (sin red: transporte simulado) -------------------

class _FakeResponse:
    def __init__(self, status_code, body):
        self.status_code, self._body = status_code, body
        self.headers = {"content-type": "application/json"}
        self.text = str(body)

    def json(self):
        return self._body


def _ok_body():
    return {"model": "m", "choices": [{"message": {"content": fake_extraction().model_dump_json()}}]}


def _patch_http(monkeypatch, responses):
    calls = []

    def fake_post(url, json, headers, timeout):
        calls.append(json)
        return responses.pop(0)

    monkeypatch.setattr("app.services.extractor.httpx.post", fake_post)
    monkeypatch.setattr("app.services.extractor.time.sleep", lambda s: None)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-test")
    return calls


def test_extractor_retries_transient_provider_errors(monkeypatch):
    error = {"error": {"code": 502, "message": "Provider returned error", "metadata": {"provider_name": "X"}}}
    calls = _patch_http(monkeypatch, [_FakeResponse(502, error), _FakeResponse(200, _ok_body())])
    extracted, _ = extractor.extract_invoice(PDF, "application/pdf", "f.pdf")
    assert extracted.invoice_number == "F001-000123"
    assert len(calls) == 2


def test_extractor_reports_provider_detail_after_retries(monkeypatch):
    error = {"error": {"code": 502, "message": "Provider returned error", "metadata": {"provider_name": "Nvidia", "raw": "overloaded"}}}
    monkeypatch.setattr(settings, "OPENROUTER_MAX_RETRIES", 1)
    calls = _patch_http(monkeypatch, [_FakeResponse(502, error), _FakeResponse(502, error)])
    with pytest.raises(ExtractionError) as exc:
        extractor.extract_invoice(PDF, "application/pdf", "f.pdf")
    assert len(calls) == 2
    assert "Nvidia" in str(exc.value) and "overloaded" in str(exc.value) and "temporal" in str(exc.value)


def test_extractor_does_not_retry_client_errors_and_sends_fallbacks(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_FALLBACK_MODELS", "a/uno, b/dos")
    calls = _patch_http(monkeypatch, [_FakeResponse(401, {"error": {"code": 401, "message": "User not found."}})])
    with pytest.raises(ExtractionError, match="401"):
        extractor.extract_invoice(PDF, "application/pdf", "f.pdf")
    assert len(calls) == 1
    assert calls[0]["models"] == [settings.OPENROUTER_MODEL, "a/uno", "b/dos"]


def test_cleanup_removes_uploads_but_keeps_manual_data(client, engine, storage_dir, extract):
    from sqlmodel import Session

    from app import cleanup

    client.post("/policies", json=POLICY)
    client.post("/vendors", json={"name": "Manual SA"})
    manual = client.post(
        "/invoices",
        json={"invoice_number": "M-1", "vendor_id": 1, "amount": 10, "currency": "PEN", "due_date": "2026-11-30"},
    ).json()
    doc = upload(client).json()  # proveedor nuevo creado por el agente
    assert doc["status"] == "processed"

    with Session(engine) as session:
        p = cleanup.plan(session)
        assert len(p["documents"]) == 1 and len(p["invoices"]) == 1 and len(p["files"]) == 1
        assert [v.name for v in p["vendors"]] == ["ACME Suministros"]
        cleanup.execute(session, p)

    assert client.get("/documents").json() == []
    assert [i["id"] for i in client.get("/invoices").json()] == [manual["id"]]
    assert [v["name"] for v in client.get("/vendors").json()] == ["Manual SA"]
    assert client.get("/policies/active").status_code == 200
    assert list(storage_dir.rglob("*.pdf")) == []


def test_deleting_invoice_removes_its_uploaded_file(client, storage_dir, extract):
    client.post("/policies", json=POLICY)  # sin tipo de cambio de PEN -> la factura queda escalada
    doc = upload(client).json()
    assert client.get(f"/invoices/{doc['invoice_id']}").json()["status"] == "escalated"
    assert len(list(storage_dir.rglob("*.pdf"))) == 1

    assert client.delete(f"/invoices/{doc['invoice_id']}").status_code == 204
    assert client.get("/documents").json() == []
    assert list(storage_dir.rglob("*.pdf")) == []
