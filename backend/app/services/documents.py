"""Procesa una factura subida: guardar → extraer con el agente → crear factura → evaluar."""
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session, select

from app.models import Document, DocumentFile, Invoice, Vendor
from app.services import agent, extractor, storage
from app.schemas import normalize_tax_id
from app.services.extractor import ExtractedInvoice, ExtractionError


class DuplicateDocument(Exception):
    def __init__(self, document: Document):
        self.document = document




def find_vendor(session: Session, name: str | None, tax_id: str | None) -> Vendor | None:
    """Busca primero por identificador fiscal y luego por nombre (sin distinguir mayúsculas)."""
    if tax_id:
        vendor = session.exec(select(Vendor).where(Vendor.tax_id == tax_id)).first()
        if vendor:
            return vendor
    if name:
        return session.exec(
            select(Vendor).where(func.lower(func.trim(Vendor.name)) == name.strip().lower())
        ).first()
    return None


def _missing_fields(data: ExtractedInvoice) -> list[str]:
    missing = []
    if not (data.vendor_name or data.vendor_tax_id):
        missing.append("proveedor")
    if not data.invoice_number:
        missing.append("número de factura")
    if data.total_amount is None or data.total_amount <= 0:
        missing.append("monto total")
    if not data.currency or len(data.currency.strip()) != 3:
        missing.append("moneda")
    return missing


def _fail(session: Session, document: Document, message: str) -> Document:
    document.status = "failed"
    document.error = message
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def process_upload(session: Session, data: bytes, original_name: str, *, is_text: bool = False) -> Document:
    """Procesa un archivo (PDF/imagen) o, con is_text, el texto de un correo o chat."""
    content_type = "text/plain" if is_text else storage.detect_type(data)[0]
    digest = storage.sha256(data)

    existing = session.exec(select(Document).where(Document.sha256 == digest)).first()
    if existing and existing.status != "failed":
        raise DuplicateDocument(existing)

    if existing:
        # Reintento de un archivo que no se pudo leer (p. ej. faltaba la API key): se reutiliza
        document = existing
        document.original_name = original_name[:255]
        document.status, document.error, document.extraction = "processing", None, None
        session.add(document)
    else:
        document = Document(
            original_name=original_name[:255],
            content_type=content_type,
            size_bytes=len(data),
            sha256=digest,
            status="processing",
        )
        session.add(document)
        session.flush()
    if session.get(DocumentFile, document.id) is None:
        session.add(DocumentFile(document_id=document.id, content=data))
    session.commit()
    session.refresh(document)

    # 1. El agente lee el documento
    try:
        extracted, meta = extractor.extract_invoice(data, content_type, original_name)
    except ExtractionError as exc:
        return _fail(session, document, str(exc))

    warnings = [w.model_dump() for w in extracted.warnings]
    extraction = {
        **meta,
        "data": extracted.model_dump(mode="json"),
        "confidence": extracted.confidence,
        "warnings": warnings,
    }
    document.extraction = extraction

    # 2. ¿Es una factura? Algunos modelos no rellenan is_invoice: si no encontró ningún dato
    #    clave y no confía en la lectura, también se trata como "no es una factura".
    missing = _missing_fields(extracted)
    if not extracted.is_invoice or (len(missing) == 4 and extracted.confidence < 0.2):
        reason = extracted.not_invoice_reason or (warnings[0]["text"] if warnings else None)
        message = "El archivo no es una factura ni una boleta"
        return _fail(session, document, f"{message}: {reason.rstrip('.')}." if reason else f"{message}.")
    if missing:
        return _fail(
            session,
            document,
            "Parece una factura, pero el agente no pudo leer: " + ", ".join(missing)
            + ". Prueba con una imagen más nítida o el PDF original.",
        )

    due_date = extracted.due_date
    if due_date is None:
        due_date = extracted.issue_date or datetime.now(UTC).date()
        # Informativo: no cambia a quién se paga ni cuánto (no escala por sí solo)
        warnings.append({
            "text": "La factura no indica fecha de vencimiento; se usó "
            + ("la fecha de emisión." if extracted.issue_date else "la fecha de hoy."),
            "critical": False,
        })

    # 2. Proveedor y duplicados
    tax_id = normalize_tax_id(extracted.vendor_tax_id)
    number = extracted.invoice_number.strip()[:100]
    vendor = find_vendor(session, extracted.vendor_name, tax_id)
    created = vendor is None

    # Si la factura ya existe, se registra igual: el agente la bloquea como duplicada y lo explica
    if vendor is not None:
        if tax_id and not vendor.tax_id:
            vendor.tax_id = tax_id
            session.add(vendor)
    else:
        # Proveedor desconocido: se crea pendiente y el agente escalará la factura
        vendor = Vendor(
            name=(extracted.vendor_name or f"Proveedor {tax_id}").strip()[:200],
            tax_id=tax_id,
            is_allowed=False,
            needs_review=True,
        )
        session.add(vendor)
        session.flush()
    extraction["vendor_created"] = created

    # 3. Se crea la factura y el agente la evalúa
    invoice = Invoice(
        invoice_number=number,
        vendor_id=vendor.id,
        amount=extracted.total_amount.quantize(Decimal("0.01")),
        currency=extracted.currency.strip().upper(),
        due_date=due_date,
        status="pending",
        raw_data={"source": "document", "document_id": document.id, "extraction": extraction},
    )
    session.add(invoice)
    session.flush()
    document.invoice_id = invoice.id
    document.extraction = extraction
    flag_modified(document, "extraction")  # los cambios in-place en JSONB no se detectan solos
    document.status = "processed"
    session.add(document)
    session.commit()
    session.refresh(invoice)

    agent.evaluate_invoice(session, invoice)
    session.refresh(document)
    return document
