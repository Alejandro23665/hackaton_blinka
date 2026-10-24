"""Archivos sintéticos para los tests (nunca documentos reales)."""
import io

from PIL import Image, ImageDraw


def image_bytes(width: int = 400, height: int = 300, fmt: str = "PNG", color: str = "white", text: str = "") -> bytes:
    image = Image.new("RGB", (width, height), color)
    if text:
        ImageDraw.Draw(image).text((10, 10), text, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def jpeg_with_orientation(width: int, height: int, orientation: int) -> bytes:
    """Foto de móvil: la imagen se guarda sin girar y la orientación va en el EXIF."""
    exif = Image.Exif()
    exif[0x0112] = orientation
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="JPEG", exif=exif.tobytes())
    return buffer.getvalue()


def pdf_bytes(pages: int, size: tuple[int, int] = (850, 1100)) -> bytes:
    images = [Image.new("RGB", size, "white") for _ in range(pages)]
    for number, image in enumerate(images, start=1):
        ImageDraw.Draw(image).text((40, 40), f"Pagina {number}", fill="black")
    buffer = io.BytesIO()
    images[0].save(buffer, format="PDF", save_all=True, append_images=images[1:])
    return buffer.getvalue()


# --- Respuestas simuladas del segmentador-clasificador ---

def detected(doc_type="DESCONOCIDO", evidence=None, number=None, continuation=False, index=1, region=None, confidence=0.95):
    return {
        "index": index,
        "doc_type": doc_type,
        "confidence": confidence,
        "evidence": evidence,
        "document_number_seen": number,
        "continuation_of_previous": continuation,
        "region": region or {"x": 0, "y": 0, "w": 1, "h": 1},
        "position_hint": "página completa",
    }


def page_response(*documents, quality="ALTA", issues=None):
    return {"page_quality": {"level": quality, "issues": issues or []}, "documents": list(documents)}


def unknown_page():
    return page_response(detected())
