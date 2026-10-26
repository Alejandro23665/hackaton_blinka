"""Registro de las llamadas a la IA (llamadas_ia) y métricas de uso y rendimiento."""
from decimal import Decimal

from sqlalchemy import text

from app.ai.client import estimate_cost
from tests.factories import detected, extraction, image_bytes, page_response, reading

INVOICE = page_response(detected("FACTURA_ELECTRONICA", "FACTURA ELECTRÓNICA", "000123"))


def _upload(client, n):
    client.post("/trabajos", files=[("files", (f"{n}.png", image_bytes(10 + n, 10), "image/png"))])


def test_every_paid_call_is_recorded_with_its_document(client, fake_ai, clean_db):
    fake_ai.pages = {1: INVOICE}
    _upload(client, 1)
    with clean_db.connect() as conn:
        rows = conn.execute(
            text("SELECT etapa, id_tanda, tokens_entrada, tokens_salida, resultado, id_documento FROM llamadas_ia ORDER BY id")
        ).all()
    doc_id = client.get("/documentos").json()["documentos"][0]["id"]
    assert rows == [
        ("CLASIFICACION", "lote1", 1000, 500, "OK", None),
        ("LECTURA_1", "lote2", 1000, 500, "OK", doc_id),
        ("LECTURA_2", "lote2", 1000, 500, "OK", doc_id),
    ]


def test_metrics_summarize_usage_and_performance(client, fake_ai, clean_db):
    fake_ai.pages = {1: INVOICE}
    fake_ai.extractions = [
        extraction(),
        extraction(DOCUMENT_NUMBER=reading("N° 2"), TOTAL_AMOUNT=reading("$ 1")),
        extraction(DOCUMENT_NUMBER=reading("N° 3"), ISSUE_DATE=reading(None, status="ILEGIBLE")),
    ]
    for n in (1, 2, 3):
        _upload(client, n)
    metrics = client.get("/metricas", params={"dias": 7}).json()

    usage = metrics["uso"]
    assert (usage["llamadas"], usage["tokens_entrada"], usage["tokens_salida"]) == (9, 9000, 4500)
    assert usage["costo_usd"] == 9 * 0.000175 and usage["documentos_leidos"] == 3
    assert usage["costo_por_documento_usd"] == round(9 * 0.000175 / 3, 6)
    assert {s["etapa"]: s["llamadas"] for s in usage["por_etapa"]} == {"CLASIFICACION": 3, "LECTURA_1": 3, "LECTURA_2": 3}
    assert len(usage["por_dia"]) == 7 and usage["por_dia"][-1]["tokens_entrada"] == 9000

    ia = metrics["ia"]
    assert (ia["documentos"], ia["sin_intervencion"], ia["pendientes"]) == (3, 1, 2)
    assert (ia["pendientes_no_legibles"], ia["pendientes_descuadre"]) == (1, 1)
    assert {c["campo"]: (c["faltante"], c["dudoso"]) for c in ia["campos"]}["fecha"] == (1, 0)

    system = metrics["sistema"]
    assert system["por_dia"][-1]["documentos"] == 3
    assert (system["tandas"], system["espera_promedio_s"], system["tasa_error"]) == (6, 30.0, 0)


def test_metrics_need_a_session(anonymous_client):
    assert anonymous_client.get("/metricas").status_code == 401


def test_cost_estimate_uses_configured_prices_and_batch_discount():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000, "cache_read_input_tokens": 1_000_000}
    # Haiku 5.5: $0,10 entrada, $0,50 salida, caché leída a 0,1x
    assert estimate_cost(usage, batch=False) == Decimal("0.610000")
    assert estimate_cost(usage, batch=True) == Decimal("0.305000")
