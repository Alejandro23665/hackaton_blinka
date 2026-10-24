"""Recepción de lotes y preprocesamiento de punta a punta (API + base de datos + almacenamiento)."""
from app.core.config import settings
from tests.factories import image_bytes, pdf_bytes


def _upload(client, *files):
    return client.post("/submissions", files=[("files", f) for f in files])


def test_lot_with_pdf_and_image_is_stored_and_split_into_pages(client, storage_dir):
    response = _upload(client, ("lote.pdf", pdf_bytes(3), "application/pdf"), ("foto.jpg", image_bytes(fmt="JPEG"), "image/jpeg"))
    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "RECIBIDO" and created["notices"] == []

    # TestClient ejecuta la tarea en segundo plano al terminar la petición
    lot = client.get(f"/submissions/{created['id']}").json()
    assert lot["status"] == "COMPLETADO"
    pdf, photo = lot["files"]
    assert (pdf["original_name"], pdf["content_type"], pdf["page_count"]) == ("lote.pdf", "application/pdf", 3)
    assert [p["page_number"] for p in pdf["pages"]] == [1, 2, 3]
    assert photo["preprocess_status"] == "LISTO" and len(photo["pages"]) == 1

    # El original y las páginas se pueden ver a través de la API
    original = client.get(f"/files/{pdf['id']}")
    assert original.status_code == 200 and original.content.startswith(b"%PDF")
    image = client.get(f"/pages/{pdf['pages'][0]['id']}/image")
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert len(list((storage_dir / "originals").rglob("*.*"))) == 2

    summary = client.get("/submissions").json()
    assert summary[0]["file_count"] == 2 and summary[0]["page_count"] == 4


def test_same_file_sent_again_is_not_duplicated(client, storage_dir):
    data = pdf_bytes(2)
    first = _upload(client, ("guia.pdf", data, "application/pdf")).json()
    second = _upload(client, ("copia.pdf", data, "application/pdf")).json()

    assert "ya se había recibido" in second["notices"][0]
    assert first["files"][0]["id"] == second["files"][0]["id"]
    assert len(list((storage_dir / "originals").rglob("*.*"))) == 1
    # El segundo lote reutiliza las páginas ya generadas
    lot = client.get(f"/submissions/{second['id']}").json()
    assert lot["status"] == "COMPLETADO" and len(lot["files"][0]["pages"]) == 2


def test_repeated_file_inside_one_lot_is_saved_once(client):
    data = image_bytes()
    created = _upload(client, ("a.png", data, "image/png"), ("b.png", data, "image/png")).json()
    assert len(created["files"]) == 1 and "repetido" in created["notices"][0]


def test_damaged_file_fails_without_losing_the_original_or_the_rest(client):
    damaged = b"%PDF-1.4 roto"
    created = _upload(client, ("roto.pdf", damaged, "application/pdf"), ("ok.png", image_bytes(), "image/png")).json()
    lot = client.get(f"/submissions/{created['id']}").json()
    assert lot["status"] == "COMPLETADO_CON_ERRORES"
    broken, ok = lot["files"]
    assert broken["preprocess_status"] == "FALLIDO" and "PDF" in broken["preprocess_error"]
    assert ok["preprocess_status"] == "LISTO"
    assert client.get(f"/files/{broken['id']}").content == damaged

    # Reprocesar reintenta lo fallido sin repetir lo hecho
    assert client.post(f"/submissions/{created['id']}/process").status_code == 202
    lot = client.get(f"/submissions/{created['id']}").json()
    assert lot["files"][0]["preprocess_status"] == "FALLIDO" and len(lot["files"][1]["pages"]) == 1


def test_invalid_lots_are_rejected_before_storing_anything(client, storage_dir, monkeypatch):
    text = _upload(client, ("nota.txt", b"hola", "text/plain"), ("ok.png", image_bytes(), "image/png"))
    assert text.status_code == 415 and "nota.txt" in text.json()["detail"]
    assert _upload(client, ("vacio.png", b"", "image/png")).status_code == 422
    monkeypatch.setattr(settings, "MAX_FILES_PER_SUBMISSION", 1)
    assert _upload(client, ("a.png", image_bytes(10, 10), "image/png"), ("b.png", image_bytes(20, 20), "image/png")).status_code == 422
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0)
    assert _upload(client, ("a.png", image_bytes(), "image/png")).status_code == 413
    assert not storage_dir.exists() or not any(storage_dir.rglob("*.*"))
    assert client.get("/submissions").json() == []


def test_unknown_ids_return_404(client):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/submissions/{missing}").status_code == 404
    assert client.get(f"/files/{missing}").status_code == 404
    assert client.get(f"/pages/{missing}/image").status_code == 404
