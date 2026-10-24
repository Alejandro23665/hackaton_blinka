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
