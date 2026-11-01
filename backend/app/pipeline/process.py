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
from pathlib import PurePosixPath
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.ai import client
from app.ai.client import AIError
from app.core.config import settings
from app.models import MODEL_ROLE, DocumentoProcesado, LlamadaIA, Rol, TipoDocumento, Usuario
from app.pipeline import extractor, images, ruts, segmenter
from app.pipeline.fields import SUBSTITUTE_RUT
from app.pipeline.grouper import GroupedDocument, group_pages
from app.pipeline.normalize import Normalized, is_other_date_label, normalize_extraction, split_tax_lines
from app.pipeline.preprocess import PreprocessError, RenderedPage, render_pages
from app.pipeline.validate import OPTIONAL_AMOUNTS, Validation, required_fields, validate
from app.storage import document_key, get_storage

# Tipo que detecta la IA → código de tipos_documentos
TYPE_CODES = {"FACTURA_ELECTRONICA": "FC", "CONTROL_INTERNO": "CI", "GUIA_DESPACHO": "GD"}
# Documento que no es FC, CI ni GD (db/011): se registra sin leer sus datos, con imagen DESC_1-9_0000
UNKNOWN_CODE = "DESC"
UNKNOWN_FOLIO = "0000"
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
    type_inferred: bool = False  # tipo deducido sin ver el título completo: lo confirma una persona
    denomination: str | None = None  # guías: GUIA_DESPACHO o GUIA_ELECTRONICA, según el título
    amounts_covered: bool = False  # la hoja adjunta tapa un dato clave: no se registra ningún importe


@dataclass
class DocumentResult:
    """Qué pasó con cada documento encontrado en el archivo (para mostrar el avance)."""

    tipo: str  # FC, CI, GD o DESC
    resultado: str  # GUARDADO, DESCARTADO, DUPLICADO o ERROR
    id: int | None = None
    folio: str | None = None
    observaciones: str | None = None
    mensaje: str | None = None


@dataclass
class FileInput:
    imagen: str  # clave del original en el almacenamiento (originals/…)
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


def _resolve_rut(
    doc_type: str, title: str | None, normalized: Normalized, extractions: list[extractor.Extraction]
) -> None:
    """Fija el RUT del emisor: el fijo del tipo de documento, el leído o el del catálogo de RUT
    conocidos de las facturas (app/pipeline/ruts.py)."""
    field = normalized.fields["PROVIDER_RUT"]
    raws = [e.fields["PROVIDER_RUT"].raw_text for e in extractions if "PROVIDER_RUT" in e.fields]
    resolution = ruts.resolve(doc_type, title, field, raws, [e.catalog_rut for e in extractions])
    if resolution.completed:
        normalized.issues = [i for i in normalized.issues if i["code"] != "RUT_SUSTITUTO"]
        normalized.issues.append(
            {
                "code": "RUT_COMPLETADO",
                "severity": "INFO",
                "field_name": "PROVIDER_RUT",
                "message": f"RUT del prestador completado como {resolution.value}: {resolution.completed}.",
                "details": {"raw_text": field.raw_text},
            }
        )
        field.status, field.value, field.invalid_reason = "LEIDO", resolution.value, None
    if resolution.value is not None and resolution.value == ruts.expected_rut(doc_type, title):
        field.low_confidence = False  # el tipo de documento ya dice cuál es: no hay nada que confirmar
    normalized.provider_rut = resolution.value or SUBSTITUTE_RUT
    normalized.rut_is_substitute = resolution.value is None


AMOUNT_NAMES = ("NET_AMOUNT", "VAT_AMOUNT", "OTHER_TAXES_AMOUNT", "EXEMPT_AMOUNT", "TOTAL_AMOUNT")


def _cover_amounts(normalized: Normalized) -> None:
    """La hoja adjunta tapa un dato clave: ningún importe del documento se registra (podría ser de la hoja)."""
    for name in AMOUNT_NAMES:
        item = normalized.fields[name]
        item.status, item.value, item.partial = "ILEGIBLE", None, None
        item.low_confidence, item.invalid_reason = False, "la hoja adjunta tapa un dato clave del documento"
    normalized.issues.append(
        {
            "code": "IMPORTES_TAPADOS",
            "severity": "ADVERTENCIA",
            "field_name": None,
            "message": "La hoja adjunta tapa un dato clave: no se registró ningún importe del documento.",
            "details": None,
        }
    )


def build_reading(
    doc_type: str, first: extractor.Extraction, second: extractor.Extraction | None, title: str | None = None
) -> Reading:
    """Normaliza y valida las dos lecturas independientes de un documento (la segunda falta si
    EXTRACTION_VERIFY está apagado). `title`: el título visto al clasificar (distingue Guía de Despacho
    de Guía Electrónica)."""
    normalized = normalize_extraction(_readings(first), _readings(second) if second else None)
    extractions = [e for e in (first, second) if e is not None]
    _resolve_rut(doc_type, title, normalized, extractions)
    # Como con los demás datos dudosos, las dos lecturas independientes deben coincidir
    covered = all(e.attached_sheet_covers_data for e in extractions)
    if covered:
        _cover_amounts(normalized)
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
    doubtful = second is not None and first.signature.present != second.signature.present
    denomination = ruts.guide_denomination(title) if doc_type == "GUIA_DESPACHO" else None
    return Reading(doc_type, normalized, validation, signed, doubtful, denomination=denomination, amounts_covered=covered)


def escalation_reasons(reading: Reading) -> list[str]:
    """Por qué el documento va a revisión humana (vacío: no va). La revisión es selectiva: la mala
    calidad de la imagen no basta. Un campo ilegible (RUT, folio, fecha, montos, un impuesto adicional) o
    una suma que no se puede comprobar dejan el documento NO_LEGIBLE, fuera de la cola.

    - Descuadre confirmado: todos los montos necesarios se leyeron y no suman el total.
    - Tipo deducido sin ver el título: duda que afecta a la clasificación.
    (Los documentos desconocidos también van a revisión: ver save_unknown.)
    """
    reasons = []
    amounts = reading.validation.amounts.values()
    # Un monto con decimales es una mala lectura (en pesos no hay decimales), no un descuadre confirmado
    misread = any(v is not None and v != v.to_integral_value() for v in amounts)
    if reading.validation.validation_status == "DESCUADRE" and not misread:
        reasons.append("descuadre")
    if reading.type_inferred:
        reasons.append("tipo deducido sin ver el título")
    return reasons


def field_problems(reading: Reading) -> tuple[list[str], list[str]]:
    """Columnas que faltan (no se leyeron) y con dudas (se leyó algo, pero no es fiable).

    - Falta: un obligatorio ausente, o ilegible sin ningún texto leído.
    - Duda: ilegible con texto (confianza baja, las dos lecturas no coinciden, formato raro), los
      montos de un descuadre, los guardados con confianza baja y la firma si una lectura la vio y la
      otra no.
    """
    fields = reading.normalized.fields
    required = required_fields(reading.doc_type, {name: f.status for name, f in fields.items()})
    missing, doubtful = set(), set()
    for name, item in fields.items():
        column = COLUMN_OF[name]
        if item.status == "ILEGIBLE":
            (doubtful if item.raw_text else missing).add(column)
        elif item.status == "AUSENTE" and name in required:
            missing.add(column)
    if reading.validation.validation_status == "DESCUADRE":
        doubtful |= {"total_neto", "iva", "total"}
        if any(reading.validation.amounts[name] is not None for name in OPTIONAL_AMOUNTS):
            doubtful.add("impuestos")
    for name, item in fields.items():
        if item.value is not None and item.low_confidence:
            doubtful.add(COLUMN_OF[name])
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
    if reading.type_inferred and observations == "LEGIBLE":
        observations = "NO_LEGIBLE"

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
        "escalado": bool(escalation_reasons(reading)),
        "denominacion": reading.denomination,
    }


# --- Guardado ---------------------------------------------------------------------------------


def type_ids(session: Session) -> dict[str, int]:
    return {t.documento: t.id for t in session.exec(select(TipoDocumento)).all()}


def model_user_id(session: Session) -> int:
    """El usuario "Modelo IA" (db/005): a su nombre queda lo que procesa la IA."""
    return session.exec(
        select(Usuario.id).join(Rol, Rol.id == Usuario.id_rol).where(Rol.rol == MODEL_ROLE).order_by(Usuario.id)
    ).first()


def save(session: Session, reading: Reading, image_key: str, folder_id: int | None = None) -> DocumentResult:
    """Guarda la fila y una copia del archivo original con el nombre TIPO_RUT_FOLIO (columna imagen)."""
    code = TYPE_CODES[reading.doc_type]
    values = row_values(reading)
    base = images.base_name(code, values["rut_proveedor"], values["folio"])
    name = images.free_name(session, base, PurePosixPath(image_key).suffix)
    row = DocumentoProcesado(
        **values,
        id_tipo_documento=type_ids(session)[code],
        imagen=name,
        id_usuario=model_user_id(session),
        id_carpeta=folder_id,
    )
    images.store_copy(image_key, name)
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        get_storage().delete(document_key(name))
        if "uq_documentos_procesados_documento" not in str(exc):
            raise
        return DocumentResult(
            code, "DUPLICADO", folio=row.folio,
            mensaje=f"Ya estaba guardado (mismo tipo, RUT {row.rut_proveedor} y folio {row.folio}).",
        )
    session.refresh(row)
    return DocumentResult(code, "GUARDADO", id=row.id, folio=row.folio, observaciones=row.observaciones)


def save_unknown(session: Session, image_key: str, folder_id: int | None = None) -> DocumentResult:
    """Registra un documento que no es FC, CI ni GD (también una nota de crédito o una hoja adjunta sola):
    tipo DESC, RUT 1-9 y folio 0000, sin datos leídos. Va a revisión humana."""
    base = f"{UNKNOWN_CODE}_{SUBSTITUTE_RUT}_{UNKNOWN_FOLIO}"
    name = images.free_name(session, base, PurePosixPath(image_key).suffix)
    row = DocumentoProcesado(
        rut_proveedor=SUBSTITUTE_RUT,
        folio=UNKNOWN_FOLIO,
        observaciones="DESCONOCIDO",
        escalado=True,
        id_tipo_documento=type_ids(session)[UNKNOWN_CODE],
        imagen=name,
        id_usuario=model_user_id(session),
        id_carpeta=folder_id,
    )
    images.store_copy(image_key, name)
    session.add(row)
    session.commit()
    session.refresh(row)
    return DocumentResult(UNKNOWN_CODE, "GUARDADO", id=row.id, folio=row.folio, observaciones=row.observaciones)


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


def legibility(reading: Reading) -> tuple[int, float]:
    """Cuánto se pudo leer de un documento: campos principales con valor y, para desempatar, la
    confianza media de lo leído."""
    fields = reading.normalized.fields
    main = ("DOCUMENT_NUMBER", "ISSUE_DATE", "NET_AMOUNT", "VAT_AMOUNT", "TOTAL_AMOUNT")
    read = [fields[name] for name in main if fields[name].value is not None]
    count = len(read) + (0 if reading.normalized.rut_is_substitute else 1)
    confidences = [item.confidence for item in read if item.confidence is not None]
    return count, sum(confidences) / len(confidences) if confidences else 0.0


def less_legible(found: list[GroupedDocument], readings: dict) -> set[int]:
    """Varias boletas en la misma página: se guarda solo la más legible (no se mezclan datos de una con
    otra). Un documento que ocupa varias páginas no compite: es un documento entero. Devuelve los
    índices de los documentos que no se guardan."""
    by_page: dict[int, list[int]] = {}
    for number, document in enumerate(found):
        pages = {region.page_id for region in document.regions}
        if number in readings and isinstance(readings[number], Reading) and len(pages) == 1:
            by_page.setdefault(pages.pop(), []).append(number)
    dropped = set()
    for numbers in by_page.values():
        if len(numbers) > 1:
            best = max(numbers, key=lambda n: legibility(readings[n]))
            dropped |= {n for n in numbers if n != best}
    return dropped


def process_files(
    session: Session,
    files: list[FileInput],
    progress: Callable[[str], None] | None = None,
    folder_id: int | None = None,
) -> list[FileOutcome]:
    """Procesa archivos ya guardados en el almacenamiento, con las llamadas a la IA en tandas.

    Los documentos guardados quedan en la carpeta folder_id (vacía si los archivos se subieron sueltos).

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
        # Lecturas de todos los documentos del archivo, para elegir el más legible de cada página
        readings_of: dict[int, Reading | AIError] = {}
        for number, document in enumerate(found):
            if document.doc_type not in TYPE_CODES:
                continue
            first, second = (results.get(f"d{index}-{number}-{reading}") for reading in (1, 2))
            failed = next((r for r in (first, second) if isinstance(r, AIError)), None)
            if failed is not None:
                readings_of[number] = failed
                continue
            reading = build_reading(
                document.doc_type, first.parsed, second.parsed if second else None, title=document.evidence
            )
            reading.type_inferred = document.type_inferred
            readings_of[number] = reading
        dropped = less_legible(found, readings_of)
        # Un archivo es desconocido (DESC) solo si no tiene ningún FC, CI ni GD. Si los tiene, lo demás
        # que se vio (hojas tapadas debajo, trozos de papel) se descarta: no es un documento del lote
        known = any(document.doc_type in TYPE_CODES for document in found)
        unknown_saved = False
        for number, document in enumerate(found):
            if document.doc_type not in TYPE_CODES:
                seen = f"título visto: {document.evidence}" if document.evidence else "sin título visible"
                if known or unknown_saved:
                    result = DocumentResult(
                        "DESC", "DESCARTADO", mensaje=f"Parte de la imagen que no es FC, CI ni GD ({seen}): se ignoró."
                    )
                else:
                    result = save_unknown(session, files[index].imagen, folder_id)
                    kind = "Nota de crédito" if "NOTA DE CREDITO" in segmenter.normalize_text(document.evidence or "") else "No es FC, CI ni GD"
                    result.mensaje = f"{kind} ({seen}): se registró como desconocido y va a revisión."
                    unknown_saved = True
                outcomes[index].documentos.append(result)
                continue
            first, second = (results.get(f"d{index}-{number}-{reading}") for reading in (1, 2))
            reading = readings_of[number]
            # Sin la segunda lectura (si está activada) no se aceptan los datos
            if isinstance(reading, AIError):
                result = DocumentResult(TYPE_CODES[document.doc_type], "ERROR", mensaje=str(reading))
            elif number in dropped:
                result = DocumentResult(
                    TYPE_CODES[document.doc_type], "DESCARTADO", folio=reading.normalized.fields["DOCUMENT_NUMBER"].value,
                    mensaje="En la misma imagen hay otra boleta más legible: se guardó solo esa.",
                )
            else:
                result = save(session, reading, files[index].imagen, folder_id)
                if document.type_inferred and result.resultado == "GUARDADO":
                    result.mensaje = f"Título no visible: tipo deducido de \"{document.evidence}\". Va a revisión."
            outcomes[index].documentos.append(result)
            record_calls(session, "LECTURA_1", first, result.id)
            record_calls(session, "LECTURA_2", second, result.id)
    return outcomes
