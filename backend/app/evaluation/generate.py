"""Genera las facturas simuladas de dataset/invoices a partir de dataset/manifest.json.

Uso (desde backend/):  python -m app.evaluation.generate

Todo el contenido es ficticio (ver dataset/README.md); las facturas no lo dicen en el propio documento
porque una factura real tampoco lo haría y el modelo lo reportaría como aviso.

Los PDF se escriben a mano (formato PDF 1.4 mínimo, una página, Helvetica) para no añadir
dependencias de producción. Los PNG usan Pillow (requirements-dev.txt).
"""
import json
import random
from decimal import Decimal

from app.evaluation import INVOICES_DIR, MANIFEST


def money(value, currency: str) -> str:
    text = f"{Decimal(str(value)):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{text} {currency}"


# Columnas de la tabla de conceptos (x en puntos PDF, desde el margen izquierdo de 50)
COLUMNS = (50, 380, 440)


def invoice_lines(company: dict, data: dict) -> list[tuple]:
    """Contenido de la factura como (texto o columnas, tamaño, negrita), de arriba abajo.

    El texto puede ser una lista de cadenas: se coloca en las posiciones de COLUMNS.
    """
    cur = data["currency"]
    lines = [
        (data["vendor_name"], 18, True),
        (f"ID fiscal: {data['vendor_tax_id']}", 10, False),
        ("", 6, False),
        (f"FACTURA N.º {data['invoice_number']}", 15, True),
    ]
    if data.get("note"):
        lines.append((data["note"], 11, True))
    lines += [
        (f"Fecha de emisión: {data['issue_date']}        Fecha de vencimiento: {data['due_date']}", 10, False),
        ("", 6, False),
        ("Facturar a:", 10, True),
        (f"{company['name']} - {company['tax_id']}", 10, False),
        (company["address"], 10, False),
        ("", 8, False),
        (["Descripción", "Cant.", "Precio unitario"], 10, True),
    ]
    for description, qty, unit in data["items"]:
        lines.append(([description[:58], str(qty), money(unit, cur)], 10, False))
    lines += [
        ("", 8, False),
        (f"Subtotal: {money(data['subtotal'], cur)}", 11, False),
        (f"{data['tax_label']}: {money(data['tax_amount'], cur)}", 11, False),
        (f"TOTAL A PAGAR: {money(data['total_amount'], cur)}", 14, True),
        (f"Moneda: {cur}", 10, False),
        ("", 8, False),
        ("Pago por transferencia internacional a la cuenta indicada en el contrato.", 8, False),
    ]
    return lines


# ---------------------------------------------------------------- PDF mínimo

def _pdf_text(value: str) -> bytes:
    raw = value.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def write_pdf(path, lines) -> None:
    content = [b"BT"]
    y = 800
    for text, size, bold in lines:
        y -= size + 6
        font = b"/F2" if bold else b"/F1"
        cells = zip(COLUMNS, text) if isinstance(text, list) else [(50, text)] if text else []
        for x, cell in cells:
            content.append(font + b" %d Tf 1 0 0 1 %d %d Tm (" % (size, x, y) + _pdf_text(cell) + b") Tj")
    content.append(b"ET")
    stream = b"\n".join(content)

    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        font % b"Helvetica",
        font % b"Helvetica-Bold",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(bytes(out))


# ---------------------------------------------------------------- PNG

def _font(size: int, bold: bool):
    from PIL import ImageFont

    for name in (("arialbd.ttf", "DejaVuSans-Bold.ttf") if bold else ("arial.ttf", "DejaVuSans.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def write_photo_png(path, lines) -> None:
    """Factura 'fotografiada': papel sobre fondo gris, algo inclinada."""
    from PIL import Image, ImageDraw

    paper = Image.new("RGB", (1240, 1460), "white")
    draw = ImageDraw.Draw(paper)
    y = 60
    for text, size, bold in lines:
        px = int(size * 2.1)
        cells = zip(COLUMNS, text) if isinstance(text, list) else [(50, text)] if text else []
        for x, cell in cells:
            draw.text((70 + int((x - 50) * 2.1), y), cell, fill=(30, 30, 35), font=_font(px, bold))
        y += px + 12
    photo = Image.new("RGB", (1500, 1700), (128, 124, 118))
    rotated = paper.rotate(2.5, expand=True, fillcolor=(128, 124, 118))
    photo.paste(rotated, (90, 70))
    photo.save(path, optimize=True)


def write_chart_png(path) -> None:
    """Imagen que NO es una factura: un gráfico de barras."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1200, 800), "white")
    draw = ImageDraw.Draw(img)
    draw.text((60, 40), "Ventas por trimestre 2026", fill=(31, 27, 45), font=_font(44, True))
    rng = random.Random(7)
    for i, label in enumerate(["Q1", "Q2", "Q3", "Q4"]):
        height = rng.randint(220, 520)
        x = 140 + i * 250
        draw.rectangle((x, 700 - height, x + 150, 700), fill=(109, 40, 217))
        draw.text((x + 50, 715), label, fill=(80, 80, 90), font=_font(32, False))
    draw.line((100, 700, 1140, 700), fill=(180, 180, 190), width=3)
    img.save(path, optimize=True)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)
    for old in INVOICES_DIR.iterdir():
        if old.is_file():
            old.unlink()

    for case in manifest["invoices"]:
        path = INVOICES_DIR / case["file"]
        data = case["data"]
        if data.get("not_invoice"):
            write_chart_png(path)
        elif path.suffix == ".png":
            write_photo_png(path, invoice_lines(manifest["company"], data))
        else:
            write_pdf(path, invoice_lines(manifest["company"], data))
        print(f"{case['id']}  {path.name}")
    print(f"\n{len(manifest['invoices'])} archivos en {INVOICES_DIR}")


if __name__ == "__main__":
    main()
