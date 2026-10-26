"""Validación del RUT del proveedor: la misma regla que el script de validación de RUT de Oxxo."""
from app.pipeline.normalize import parse_rut, rut_check_digit
from tests.factories import detected, extraction, image_bytes, page_response, reading


def _oxxo_script(rut: str) -> tuple[bool, str | None]:
    """Traducción línea a línea del script VBScript de Oxxo (Mid, Right, Left, Mod…)."""
    position = rut.find("-") + 1  # Instr: 1-indexado, 0 si no está
    body = rut[: position - 1] if position > 0 else ""
    check = rut[-1:]
    rut = body + check
    if len(rut) < 2:
        return False, "Formato Rut incorrecto o vacío"
    body, check = rut[:-1], rut[-1:]
    if not body.isdigit():
        return False, "Cuerpo no es numérico"
    number, total, j = body, 0, 2
    for i in range(1, len(body) + 1):
        number = number[: len(body) - i + 1]
        total += j * int(number[-1])
        j = 2 if j + 1 > 7 else j + 1
    i = 11 - (total % 11)
    digit = str(i) if i < 10 else ("K" if i == 10 else "0")
    if check != digit:
        return False, f"Digito verificador invalido, ingresado: {check}, esperado: {digit}"
    return True, None


def test_check_digit_matches_the_oxxo_script_for_every_body():
    # Todos los cuerpos de 1 a 300.000 y un barrido de RUT de empresas (70 a 99 millones)
    bodies = list(range(1, 300_001)) + list(range(70_000_000, 100_000_000, 9_973))
    for body in bodies:
        digit = rut_check_digit(body)
        assert _oxxo_script(f"{body}-{digit}") == (True, None), body
        wrong = "0" if digit != "0" else "1"
        assert _oxxo_script(f"{body}-{wrong}")[0] is False


def test_known_ruts():
    assert parse_rut("76.084.682-1").value == "76084682-1"  # OXXO
    assert parse_rut("R.U.T.: 93.178.000-k").value == "93178000-K"
    assert parse_rut("91144000-8").value == "91144000-8"


def test_invalid_ruts_are_rejected_with_the_same_reasons():
    assert parse_rut("76.084.682-5").reason == "dígito verificador inválido, ingresado: 5, esperado: 1"
    assert "no es numérico" in parse_rut("7A.084.682-1").reason
    assert "vacío" in parse_rut("0-0").reason


def test_document_with_invalid_rut_goes_to_human_review(client, fake_ai):
    # La IA lee el RUT con seguridad, pero su dígito verificador no corresponde
    fake_ai.pages = {1: page_response(detected("CONTROL_INTERNO", "CONTROL INTERNO", "2388"))}
    fake_ai.extractions = [extraction(PROVIDER_RUT=reading("76.084.682-5"))]
    client.post("/trabajos", files=[("files", ("a.png", image_bytes(), "image/png"))])
    (doc,) = client.get("/documentos").json()["documentos"]
    assert (doc["rut_proveedor"], doc["observaciones"], doc["requiere_revision"]) == ("1-9", "NO_LEGIBLE", True)
    assert doc["campos_dudosos"] == ["rut_proveedor"]
    # Al corregir, el revisor tampoco puede guardar un RUT inválido
    fix = {
        "tipo": "CI", "rut_proveedor": "76.084.682-5", "folio": "2388", "fecha": "2026-10-14", "firma": True,
        "total_neto": 100000, "iva": 19000, "impuestos": None, "total": 119000,
    }
    response = client.put(f"/documentos/{doc['id']}/correccion", json=fix)
    assert response.status_code == 422 and "esperado: 1" in response.json()["detail"]
    assert client.put(f"/documentos/{doc['id']}/correccion", json={**fix, "rut_proveedor": "76.084.682-1"}).status_code == 200
