"""Preprocesador y almacenamiento: sin base de datos ni IA."""
import io

import pytest
from PIL import Image

from app.core.config import settings
from app.pipeline.preprocess import PreprocessError, UnsupportedFile, detect_type, render_pages
from app.storage import LocalStorage, original_key, page_key
from tests.factories import image_bytes, jpeg_with_orientation, pdf_bytes


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def test_detects_type_by_content_not_by_name():
    assert detect_type(pdf_bytes(1)) == ("application/pdf", ".pdf")
    assert detect_type(image_bytes(fmt="PNG")) == ("image/png", ".png")
    assert detect_type(image_bytes(fmt="JPEG")) == ("image/jpeg", ".jpg")
    assert detect_type(image_bytes(fmt="WEBP")) == ("image/webp", ".webp")
    with pytest.raises(UnsupportedFile):
        detect_type(b"hola, esto es texto")
    with pytest.raises(UnsupportedFile):
        detect_type(image_bytes(fmt="GIF"))


def test_pdf_becomes_one_jpeg_per_page():
    pages = render_pages(pdf_bytes(3), "application/pdf")
    assert [p.number for p in pages] == [1, 2, 3]
    for page in pages:
        image = _open(page.data)
        assert image.format == "JPEG" and image.size == (page.width, page.height)


def test_image_is_one_page():
    pages = render_pages(image_bytes(640, 480), "image/png")
    assert len(pages) == 1 and (pages[0].width, pages[0].height) == (640, 480)


def test_phone_photo_is_rotated_upright():
    # Orientación 6: la cámara guardó la foto acostada; hay que girarla 90°
    pages = render_pages(jpeg_with_orientation(400, 200, orientation=6), "image/jpeg")
    assert (pages[0].width, pages[0].height) == (200, 400)


def test_large_pages_are_limited_to_max_side():
    pages = render_pages(image_bytes(5000, 2500), "image/png")
    assert max(pages[0].width, pages[0].height) == settings.PAGE_MAX_SIDE_PX
    assert pages[0].width == 2 * pages[0].height  # se conserva la proporción


def test_transparent_png_gets_white_background():
    buffer = io.BytesIO()
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(buffer, format="PNG")
    image = _open(render_pages(buffer.getvalue(), "image/png")[0].data).convert("RGB")
    assert image.getpixel((25, 25))[0] > 240


def test_damaged_files_raise_preprocess_error():
    with pytest.raises(PreprocessError):
        render_pages(b"%PDF-1.4 esto no es un pdf", "application/pdf")
    with pytest.raises(PreprocessError):
        render_pages(image_bytes(fmt="PNG")[:60], "image/png")


def test_pdf_page_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_PAGES_PER_FILE", 2)
    with pytest.raises(PreprocessError, match="3 páginas"):
        render_pages(pdf_bytes(3), "application/pdf")


def test_local_storage_roundtrip_and_rejects_unsafe_keys(tmp_path):
    storage = LocalStorage(tmp_path)
    key = original_key("ab" * 32, ".pdf")
    storage.put(key, b"contenido")
    assert storage.exists(key) and storage.get(key) == b"contenido"
    assert storage.exists(page_key("ab" * 32, 1)) is False
    for bad in ("../fuera.txt", "/absoluta.pdf", "a/../../b.pdf", "sin-extension"):
        with pytest.raises(ValueError):
            storage.put(bad, b"x")
