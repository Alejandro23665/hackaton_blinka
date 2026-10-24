"""Preprocesador (código, sin IA): convierte un archivo en imágenes de página listas para la IA.

- PDF: cada página se dibuja como imagen (pypdfium2, el motor de PDF de Chrome).
- Imagen: se corrige la orientación de las fotos del móvil (EXIF) y se pasa a RGB.
- Todas: se limita el lado mayor (PAGE_MAX_SIDE_PX) y se guardan como JPEG.

Imágenes más grandes no mejoran la lectura y hacen las llamadas a la IA más lentas y caras.
"""
import io
from dataclasses import dataclass

import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

# firma inicial -> (content_type, extensión). El tipo se detecta por el contenido, no por el nombre.
_SIGNATURES = [
    (b"%PDF-", ("application/pdf", ".pdf")),
    (b"\x89PNG\r\n\x1a\n", ("image/png", ".png")),
    (b"\xff\xd8\xff", ("image/jpeg", ".jpg")),
]

ALLOWED_DESCRIPTION = "PDF, JPG, PNG o WEBP"
JPEG_QUALITY = 90


class UnsupportedFile(ValueError):
    """El archivo no es de un tipo admitido (se rechaza al subirlo)."""


class PreprocessError(Exception):
    """El archivo es de un tipo admitido pero no se puede abrir (dañado, protegido, demasiado grande)."""


@dataclass
class RenderedPage:
    number: int
    data: bytes
    width: int
    height: int


def detect_type(data: bytes) -> tuple[str, str]:
    for signature, kind in _SIGNATURES:
        if data.startswith(signature):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise UnsupportedFile(f"Formato no soportado. Sube un archivo {ALLOWED_DESCRIPTION}.")


def _to_jpeg(image: Image.Image, number: int) -> RenderedPage:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        # Lo transparente se pone blanco, como el papel
        rgba = image.convert("RGBA")
        image = Image.new("RGB", rgba.size, "white")
        image.paste(rgba, mask=rgba.getchannel("A"))
    elif image.mode != "RGB":
        image = image.convert("RGB")
    max_side = settings.PAGE_MAX_SIDE_PX
    image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return RenderedPage(number=number, data=buffer.getvalue(), width=image.width, height=image.height)


def _render_pdf(data: bytes) -> list[RenderedPage]:
    try:
        pdf = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise PreprocessError(f"No se pudo abrir el PDF (dañado o protegido con contraseña): {exc}") from exc
    try:
        total = len(pdf)
        if total == 0:
            raise PreprocessError("El PDF no tiene páginas")
        if total > settings.MAX_PAGES_PER_FILE:
            raise PreprocessError(f"El PDF tiene {total} páginas; el máximo es {settings.MAX_PAGES_PER_FILE}")
        pages = []
        for index in range(total):
            page = pdf[index]
            try:
                width_pt, height_pt = page.get_size()
                # Resolución PAGE_RENDER_DPI, salvo que la página sea enorme: se dibuja ya al tamaño final
                scale = min(settings.PAGE_RENDER_DPI / 72, settings.PAGE_MAX_SIDE_PX / max(width_pt, height_pt, 1))
                image = page.render(scale=scale).to_pil()
                pages.append(_to_jpeg(image, index + 1))
            except pdfium.PdfiumError as exc:
                raise PreprocessError(f"No se pudo dibujar la página {index + 1}: {exc}") from exc
            finally:
                page.close()
        return pages
    finally:
        pdf.close()


def _render_image(data: bytes) -> list[RenderedPage]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            # Las fotos del móvil guardan la orientación aparte: se aplica para que el texto quede derecho
            upright = ImageOps.exif_transpose(image)
            return [_to_jpeg(upright, 1)]
    except Image.DecompressionBombError as exc:
        raise PreprocessError("La imagen es demasiado grande para procesarla") from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise PreprocessError(f"No se pudo abrir la imagen (archivo dañado o incompleto): {exc}") from exc


def render_pages(data: bytes, content_type: str) -> list[RenderedPage]:
    if content_type == "application/pdf":
        return _render_pdf(data)
    return _render_image(data)
