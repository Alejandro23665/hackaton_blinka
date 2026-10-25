"""Procesamiento de un archivo (imagen o PDF) hasta documentos_procesados.

Pasos: páginas → [IA] segmentar y clasificar cada página → agrupar en documentos → en cada
documento admitido, [IA] dos lecturas independientes → normalizar → validar → una fila en
documentos_procesados.

- Los documentos desconocidos se descartan: no se guardan.
- Un documento ya guardado (mismo tipo, RUT y folio) no se repite: la base lo rechaza.
- "La IA lee, el código decide": normalizar, sumar y fijar observaciones lo hace código probado.
"""
import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.ai.client import AIError
from app.core.config import settings
from app.models import DocumentoProcesado, TipoDocumento
from app.pipeline import extractor, segmenter
from app.pipeline.grouper import GroupedDocument, group_pages
from app.pipeline.normalize import Normalized, normalize_extraction, split_tax_lines
from app.pipeline.preprocess import RenderedPage, render_pages
from app.pipeline.validate import Validation, validate
from app.storage import get_storage

# Tipo que detecta la IA → código de tipos_documentos
TYPE_CODES = {"FACTURA_ELECTRONICA": "FC", "CONTROL_INTERNO": "CI", "GUIA_DESPACHO": "GD"}
# Estado del validador → observaciones
OBSERVATIONS = {"PROCESADO": "LEGIBLE", "NO_LEGIBLE": "NO_LEGIBLE", "DESCUADRE": "DESCUADRE"}
# Errores de la IA que no se arreglan reintentando el siguiente documento
STOP_CODES = ("CUOTA", "SIN_CLAVE", "CLAVE")

logger = logging.getLogger(__name__)


class QuotaExhausted(Exception):
    """Se agotó la cuota de la IA (o falta la clave): no tiene sentido seguir con el resto."""


@dataclass
class Reading:
    """Lo leído y decidido de un documento, antes de guardarlo."""

    doc_type: str
    normalized: Normalized
    validation: Validation
    signed: bool


@dataclass
class DocumentResult:
    """Qué pasó con cada documento encontrado en el archivo (para mostrar el avance)."""

    tipo: str  # FC, CI, GD o DESCONOCIDO
    resultado: str  # GUARDADO, DESCARTADO, DUPLICADO o ERROR
    id: int | None = None
    folio: str | None = None
    observaciones: str | None = None
    mensaje: str | None = None


# --- Lectura (IA + código, sin base de datos) -----------------------------------------------


def _readings(extraction: extractor.Extraction) -> dict[str, dict]:
    """Lecturas por campo para el normalizador. Los impuestos van como líneas: el código separa el IVA
    de los demás (IABA, ILA…) y los suma."""
    readings = {name: reading.model_dump() for name, reading in extraction.fields.items()}
    vat_lines, other_lines = split_tax_lines([line.model_dump() for line in extraction.tax_lines])
    readings["VAT_AMOUNT"] = {"lines": vat_lines}
    readings["OTHER_TAXES_AMOUNT"] = {"lines": other_lines}
    return readings


def read_document(doc_type: str, images: list[tuple[bytes, str]]) -> Reading:
    """Dos lecturas independientes, normalización y validación. Lanza AIError si la IA falla:
    sin la segunda lectura no se aceptan los datos."""
    first: extractor.Extraction = extractor.extract_document(doc_type, images, temperature=0).parsed
    second = None
    if settings.EXTRACTION_VERIFY:
        second = extractor.extract_document(doc_type, images, temperature=settings.VERIFY_TEMPERATURE).parsed
    normalized = normalize_extraction(_readings(first), _readings(second) if second else None)
    values = {name: item.value for name, item in normalized.fields.items()}
    if normalized.rut_is_substitute:
        values["PROVIDER_RUT"] = None
    validation = validate(
        doc_type,
        {name: item.status for name, item in normalized.fields.items()},
        values,
        Decimal(settings.TOTAL_TOLERANCE_CLP),
    )
    # Firmado solo si las dos lecturas ven la firma: dar por recibido algo sin firma es peor
    signed = first.signature.present and (second is None or second.signature.present)
    return Reading(doc_type, normalized, validation, signed)


def row_values(reading: Reading) -> dict:
    """Columnas de documentos_procesados a partir de lo leído (sin tipo ni imagen)."""
    amounts = reading.validation.amounts
    observations = OBSERVATIONS[reading.validation.overall_status]
    # En pesos chilenos no hay decimales: un monto con decimales es una mala lectura
    if any(v is not None and v != v.to_integral_value() for v in amounts.values()):
        observations = "NO_LEGIBLE"
        amounts = {name: Decimal(0) for name in amounts}

    def whole(value):
        return None if value is None else int(value)

    other, exempt = amounts["OTHER_TAXES_AMOUNT"], amounts["EXEMPT_AMOUNT"]
    fields = reading.normalized.fields
    return {
        "rut_proveedor": reading.normalized.provider_rut,
        "folio": fields["DOCUMENT_NUMBER"].value,
        "fecha": fields["ISSUE_DATE"].value,
        "firma": reading.signed,
        # El exento va sumado con los otros impuestos; el IVA, aparte
        "impuestos": None if other is None and exempt is None else whole((other or 0) + (exempt or 0)),
        "total_neto": whole(amounts["NET_AMOUNT"]),
        "iva": whole(amounts["VAT_AMOUNT"]),
        "total": whole(amounts["TOTAL_AMOUNT"]),
        "observaciones": observations,
    }


# --- Guardado ---------------------------------------------------------------------------------


def type_ids(session: Session) -> dict[str, int]:
    return {t.documento: t.id for t in session.exec(select(TipoDocumento)).all()}


def save(session: Session, reading: Reading, image_key: str) -> DocumentResult:
    code = TYPE_CODES[reading.doc_type]
    row = DocumentoProcesado(**row_values(reading), id_tipo_documento=type_ids(session)[code], imagen=image_key)
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if "uq_documentos_procesados_documento" not in str(exc):
            raise
        return DocumentResult(
            code, "DUPLICADO", folio=row.folio,
            mensaje=f"Ya estaba guardado (mismo tipo, RUT {row.rut_proveedor} y folio {row.folio}).",
        )
    session.refresh(row)
    return DocumentResult(code, "GUARDADO", id=row.id, folio=row.folio, observaciones=row.observaciones)


# --- Un archivo completo ----------------------------------------------------------------------


def _document_images(document: GroupedDocument, pages: dict[int, RenderedPage]) -> list[tuple[bytes, str]]:
    """La imagen de cada parte del documento: la página completa o el recorte de su zona."""
    images = []
    for number, region in enumerate(document.regions, start=1):
        page = pages[region.page_id]
        description = f"hoja {number} de {len(document.regions)} (página {page.number} del archivo)"
        jpeg = page.data
        if region.bbox:
            jpeg = extractor.crop(jpeg, region.bbox)
            description += f", recorte de la zona {region.position_hint or 'indicada'}"
        images.append((jpeg, description))
    return images


def _segment(pages: list[RenderedPage]) -> list[GroupedDocument]:
    analyses = []
    previous: str | None = None
    for page in pages:
        analysis = segmenter.analyze_page(page.data, page.number, len(pages), previous).parsed
        analyses.append((page.number, analysis))
        last = max(analysis.documents, key=lambda d: d.index)
        previous = segmenter.describe(last.doc_type, last.document_number_seen)
    return group_pages(analyses)


def process_file(session: Session, image_key: str, content_type: str) -> list[DocumentResult]:
    """Procesa un archivo ya guardado en el almacenamiento. Lanza QuotaExhausted si la IA se queda
    sin cuota (lo ya guardado se conserva), PreprocessError si el archivo no se puede abrir y
    AIError si la IA no pudo clasificar una página."""
    pages = {page.number: page for page in render_pages(get_storage().get(image_key), content_type)}
    try:
        documents = _segment(list(pages.values()))
    except AIError as exc:
        if exc.code in STOP_CODES:
            raise QuotaExhausted(str(exc)) from exc
        raise

    results = []
    for document in documents:
        if document.doc_type not in TYPE_CODES:
            seen = f"título visto: {document.evidence}" if document.evidence else "sin título visible"
            results.append(DocumentResult("DESCONOCIDO", "DESCARTADO", mensaje=f"No es FC, CI ni GD ({seen})."))
            continue
        try:
            reading = read_document(document.doc_type, _document_images(document, pages))
        except AIError as exc:
            if exc.code in STOP_CODES:
                raise QuotaExhausted(str(exc)) from exc
            results.append(DocumentResult(TYPE_CODES[document.doc_type], "ERROR", mensaje=str(exc)))
            continue
        results.append(save(session, reading, image_key))
    return results
