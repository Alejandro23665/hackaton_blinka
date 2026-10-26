"""Procesamiento de archivos (imágenes o PDF) hasta documentos_procesados.

Pasos: páginas → [IA] segmentar y clasificar cada página → agrupar en documentos → en cada
documento admitido, [IA] dos lecturas independientes → normalizar → validar → una fila en
documentos_procesados.

Las llamadas a la IA van en tandas (Message Batches): una con las páginas de todos los archivos (en
un PDF, una ronda por número de página, porque cada página necesita saber cómo terminó la anterior)
y otra con las dos lecturas de todos los documentos.

- Los documentos desconocidos se descartan: no se guardan.
- Un documento ya guardado (mismo tipo, RUT y folio) no se repite: la base lo rechaza.
- "La IA lee, el código decide": normalizar, sumar y fijar observaciones lo hace código probado.
- Cada fila queda a nombre del usuario "Modelo IA" y con los campos que faltan o tienen dudas, para
  que una persona los corrija en la revisión.
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.ai import client
from app.ai.client import AIError
from app.core.config import settings
from app.models import MODEL_ROLE, DocumentoProcesado, LlamadaIA, Rol, TipoDocumento, Usuario
from app.pipeline import extractor, segmenter
from app.pipeline.grouper import GroupedDocument, group_pages
from app.pipeline.normalize import Normalized, is_other_date_label, normalize_extraction, split_tax_lines
from app.pipeline.preprocess import PreprocessError, RenderedPage, render_pages
from app.pipeline.validate import OPTIONAL_AMOUNTS, Validation, required_fields, validate
from app.storage import get_storage

# Tipo que detecta la IA → código de tipos_documentos
TYPE_CODES = {"FACTURA_ELECTRONICA": "FC", "CONTROL_INTERNO": "CI", "GUIA_DESPACHO": "GD"}
# Estado del validador → observaciones
OBSERVATIONS = {"PROCESADO": "LEGIBLE", "NO_LEGIBLE": "NO_LEGIBLE", "DESCUADRE": "DESCUADRE"}
# Campo del extractor → columna de documentos_procesados (otros impuestos y exento van juntos)
COLUMN_OF = {
    "PROVIDER_RUT": "rut_proveedor",
    "DOCUMENT_NUMBER": "folio",
    "ISSUE_DATE": "fecha",
    "NET_AMOUNT": "total_neto",
    "VAT_AMOUNT": "iva",
    "OTHER_TAXES_AMOUNT": "impuestos",
    "EXEMPT_AMOUNT": "impuestos",
    "TOTAL_AMOUNT": "total",
}
# Orden en que se listan los campos con problemas
COLUMNS = ("rut_proveedor", "folio", "fecha", "firma", "total_neto", "iva", "impuestos", "total")

logger = logging.getLogger(__name__)


class AIUnavailable(Exception):
    """No se puede usar la IA (falta la clave, fue rechazada, sin saldo…): no tiene sentido seguir."""


@dataclass
class Reading:
    """Lo leído y decidido de un documento, antes de guardarlo."""

    doc_type: str
    normalized: Normalized
    validation: Validation
    signed: bool
    signature_doubtful: bool = False  # una lectura vio la firma y la otra no


@dataclass
class DocumentResult:
    """Qué pasó con cada documento encontrado en el archivo (para mostrar el avance)."""

    tipo: str  # FC, CI, GD o DESCONOCIDO
    resultado: str  # GUARDADO, DESCARTADO, DUPLICADO o ERROR
    id: int | None = None
    folio: str | None = None
    observaciones: str | None = None
    mensaje: str | None = None


@dataclass
class FileInput:
    imagen: str  # clave del original en el almacenamiento
    tipo_contenido: str


@dataclass
class FileOutcome:
    documentos: list[DocumentResult] = field(default_factory=list)
    error: str | None = None  # el archivo no se pudo procesar


# --- Lectura (IA + código, sin base de datos) -----------------------------------------------


def _readings(extraction: extractor.Extraction) -> dict[str, dict]:
    """Lecturas por campo para el normalizador. Los impuestos van como líneas: el código separa el IVA
    de los demás (IABA, ILA…) y los suma."""
    readings = {name: reading.model_dump() for name, reading in extraction.fields.items()}
    # La fecha que trae otro rótulo (referencia, vencimiento, orden de compra) no es la de emisión
    date = readings.get("ISSUE_DATE")
    if date and date.get("status") == "LEIDO" and is_other_date_label(extraction.date_label):
        readings["ISSUE_DATE"] = {**date, "status": "ILEGIBLE"}
    vat_lines, other_lines = split_tax_lines([line.model_dump() for line in extraction.tax_lines])
    readings["VAT_AMOUNT"] = {"lines": vat_lines}
    readings["OTHER_TAXES_AMOUNT"] = {"lines": other_lines}
    return readings


def build_reading(doc_type: str, first: extractor.Extraction, second: extractor.Extraction | None) -> Reading:
    """Normaliza y valida las dos lecturas independientes de un documento (la segunda falta si
    EXTRACTION_VERIFY está apagado)."""
    normalized = normalize_extraction(_readings(first), _readings(second) if second else None)
    values = {name: item.value for name, item in normalized.fields.items()}
    if normalized.rut_is_substitute:
        values["PROVIDER_RUT"] = None
    validation = validate(
        doc_type,
        {name: item.status for name, item in normalized.fields.items()},
        values,
        Decimal(settings.TOTAL_TOLERANCE_CLP),
        partial={name: item.partial for name, item in normalized.fields.items() if item.partial is not None},
    )
    # Firmado solo si las dos lecturas ven la firma: dar por recibido algo sin firma es peor
    signed = first.signature.present and (second is None or second.signature.present)
    doubtful = second is not None and first.signature.present != second.signature.present
    return Reading(doc_type, normalized, validation, signed, doubtful)


def field_problems(reading: Reading) -> tuple[list[str], list[str]]:
    """Columnas que faltan (no se leyeron) y con dudas (se leyó algo, pero no es fiable).

    - Falta: un obligatorio ausente, o ilegible sin ningún texto leído.
    - Duda: ilegible con texto (confianza baja, las dos lecturas no coinciden, formato raro), los
      montos de un descuadre y la firma si una lectura la vio y la otra no.
    - Un opcional ilegible que se dedujo en 0 (los demás montos ya suman el total) no es problema.
    """
    fields = reading.normalized.fields
    required = required_fields(reading.doc_type, {name: f.status for name, f in fields.items()})
    deduced = {i["field_name"] for i in reading.validation.issues if i["code"] == "OPCIONAL_DEDUCIDO"}
    missing, doubtful = set(), set()
    for name, item in fields.items():
        column = COLUMN_OF[name]
        if item.status == "ILEGIBLE" and name not in deduced:
            (doubtful if item.raw_text else missing).add(column)
        elif item.status == "AUSENTE" and name in required:
            missing.add(column)
    if reading.validation.validation_status == "DESCUADRE":
        doubtful |= {"total_neto", "iva", "total"}
        if any(reading.validation.amounts[name] is not None for name in OPTIONAL_AMOUNTS):
            doubtful.add("impuestos")
    if reading.signature_doubtful:
        doubtful.add("firma")
    doubtful -= missing
    return [c for c in COLUMNS if c in missing], [c for c in COLUMNS if c in doubtful]


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
    # Otros impuestos o exento que no se leyeron (ni se dedujeron ni quedaron en 0 por la regla de montos)
    unreadable_taxes = any(
        fields[name].status == "ILEGIBLE" and amounts[name] is None for name in ("OTHER_TAXES_AMOUNT", "EXEMPT_AMOUNT")
    )
    missing, doubtful = field_problems(reading)
    return {
        "rut_proveedor": reading.normalized.provider_rut,
        "folio": fields["DOCUMENT_NUMBER"].value,
        "fecha": fields["ISSUE_DATE"].value,
        "firma": reading.signed,
        # El exento va sumado con los otros impuestos; el IVA, aparte. Si uno de los dos no se leyó, la
        # suma no se conoce: queda vacía (nunca 0)
        "impuestos": None if unreadable_taxes or (other is None and exempt is None) else whole((other or 0) + (exempt or 0)),
        "total_neto": whole(amounts["NET_AMOUNT"]),
        "iva": whole(amounts["VAT_AMOUNT"]),
        "total": whole(amounts["TOTAL_AMOUNT"]),
        "observaciones": observations,
        "campos_faltantes": missing,
        "campos_dudosos": doubtful,
    }


# --- Guardado ---------------------------------------------------------------------------------


def type_ids(session: Session) -> dict[str, int]:
    return {t.documento: t.id for t in session.exec(select(TipoDocumento)).all()}


def model_user_id(session: Session) -> int:
    """El usuario "Modelo IA" (db/005): a su nombre queda lo que procesa la IA."""
    return session.exec(
        select(Usuario.id).join(Rol, Rol.id == Usuario.id_rol).where(Rol.rol == MODEL_ROLE).order_by(Usuario.id)
    ).first()


def save(session: Session, reading: Reading, image_key: str) -> DocumentResult:
    code = TYPE_CODES[reading.doc_type]
    row = DocumentoProcesado(
        **row_values(reading),
        id_tipo_documento=type_ids(session)[code],
        imagen=image_key,
        id_usuario=model_user_id(session),
    )
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


# --- Archivos completos ----------------------------------------------------------------------


def _document_images(document: GroupedDocument, pages: dict[int, RenderedPage]) -> list[tuple[bytes, str]]:
    """La imagen de cada parte del documento: la página completa o, si comparte la página con otros,
    el recorte de su zona seguido de la página completa (la zona que marca la IA puede quedar corta:
    por ejemplo, solo la cabecera de una factura cuyo pie sigue debajo de una hoja corcheteada)."""
    images = []
    for number, region in enumerate(document.regions, start=1):
        page = pages[region.page_id]
        description = f"hoja {number} de {len(document.regions)} (página {page.number} del archivo)"
        if not region.bbox:
            images.append((page.data, description))
            continue
        images.append((extractor.crop(page.data, region.bbox), f"{description}, recorte de la zona {region.position_hint or 'indicada'}"))
        images.append((
            page.data,
            f"{description}, página completa como contexto: el documento es el del recorte anterior; si continúa "
            "fuera del recorte (por ejemplo debajo de una hoja superpuesta), lee aquí esa parte; no leas otros documentos",
        ))
    return images


def record_calls(session: Session, stage: str, outcome, document_id: int | None = None) -> None:
    """Registra en llamadas_ia los intentos pagados de una solicitud (la caché no tiene ninguno)."""
    for call in getattr(outcome, "calls", None) or []:
        session.add(
            LlamadaIA(
                etapa=stage,
                modelo=call.model,
                id_tanda=call.batch_id,
                tokens_entrada=call.input_tokens,
                tokens_salida=call.output_tokens,
                costo_usd=call.cost_usd,
                espera_s=Decimal(str(call.wait_s)),
                resultado=call.outcome if call.outcome in ("OK", "RECHAZO", "FORMATO") else "ERROR",
                id_documento=document_id,
            )
        )
    session.commit()


def _ask(requests: list[client.AIRequest], progress: Callable[[str], None]) -> dict:
    try:
        return client.run(requests, progress)
    except AIError as exc:
        raise AIUnavailable(str(exc)) from exc


def _segment(
    session: Session, files: dict[int, dict[int, RenderedPage]], outcomes: list[FileOutcome], progress
) -> dict[int, list]:
    """Clasifica las páginas de todos los archivos. Ronda N: la página N de cada archivo que la tenga."""
    analyses: dict[int, list] = {index: [] for index in files}
    previous: dict[int, str | None] = {index: None for index in files}
    rounds = max((len(pages) for pages in files.values()), default=0)
    for number in range(1, rounds + 1):
        requests = {
            f"p{index}-{number}": (
                index,
                segmenter.page_request(f"p{index}-{number}", pages[number].data, number, len(pages), previous[index]),
            )
            for index, pages in files.items()
            if outcomes[index].error is None and number in pages
        }
        if not requests:
            break
        stage = f"Clasificando páginas (ronda {number} de {rounds})" if rounds > 1 else "Clasificando páginas"
        results = _ask([request for _, request in requests.values()], lambda text: progress(f"{stage}. {text}"))
        for key, (index, _) in requests.items():
            result = results[key]
            record_calls(session, "CLASIFICACION", result)
            if isinstance(result, AIError):
                outcomes[index].error = f"No se pudo clasificar la página {number}: {result}"
                continue
            analyses[index].append((number, result.parsed))
            last = max(result.parsed.documents, key=lambda d: d.index)
            previous[index] = segmenter.describe(last.doc_type, last.document_number_seen)
    return analyses


def process_files(
    session: Session, files: list[FileInput], progress: Callable[[str], None] | None = None
) -> list[FileOutcome]:
    """Procesa archivos ya guardados en el almacenamiento, con las llamadas a la IA en tandas.

    Devuelve, por archivo, qué pasó con cada documento (o por qué no se pudo procesar). Lanza
    AIUnavailable si no se puede usar la IA.
    """
    progress = progress or (lambda _text: None)
    outcomes = [FileOutcome() for _ in files]
    storage = get_storage()
    rendered: dict[int, dict[int, RenderedPage]] = {}
    for index, item in enumerate(files):
        try:
            pages = render_pages(storage.get(item.imagen), item.tipo_contenido)
            rendered[index] = {page.number: page for page in pages}
        except PreprocessError as exc:
            outcomes[index].error = str(exc)

    analyses = _segment(session, rendered, outcomes, progress)
    documents = {index: group_pages(analyses[index]) for index in rendered if outcomes[index].error is None}

    readings = (1, 2) if settings.EXTRACTION_VERIFY else (1,)
    requests = [
        extractor.document_request(
            f"d{index}-{number}-{reading}", document.doc_type, _document_images(document, rendered[index]), reading
        )
        for index, found in documents.items()
        for number, document in enumerate(found)
        if document.doc_type in TYPE_CODES
        for reading in readings
    ]
    results = _ask(requests, lambda text: progress(f"Leyendo documentos. {text}")) if requests else {}

    progress("Guardando")
    for index, found in documents.items():
        for number, document in enumerate(found):
            if document.doc_type not in TYPE_CODES:
                seen = f"título visto: {document.evidence}" if document.evidence else "sin título visible"
                outcomes[index].documentos.append(
                    DocumentResult("DESCONOCIDO", "DESCARTADO", mensaje=f"No es FC, CI ni GD ({seen}).")
                )
                continue
            first, second = (results.get(f"d{index}-{number}-{reading}") for reading in (1, 2))
            # Sin la segunda lectura (si está activada) no se aceptan los datos
            failed = next((r for r in (first, second) if isinstance(r, AIError)), None)
            if failed is not None:
                result = DocumentResult(TYPE_CODES[document.doc_type], "ERROR", mensaje=str(failed))
            else:
                reading = build_reading(document.doc_type, first.parsed, second.parsed if second else None)
                result = save(session, reading, files[index].imagen)
            outcomes[index].documentos.append(result)
            record_calls(session, "LECTURA_1", first, result.id)
            record_calls(session, "LECTURA_2", second, result.id)
    return outcomes
