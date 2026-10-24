"""Agrupador (código, sin IA): convierte lo que el segmentador vio en cada página en documentos.

- Una región que es continuación del último documento de la página anterior (mismo tipo y mismo
  número, o número no visible) se une a ese documento: una factura de 3 hojas es un documento.
- Todo lo demás abre un documento nuevo. Si la continuación no cuadra, se separa y se avisa:
  es mejor separar de más que mezclar dos facturas en una.
- Cada región desconocida es su propio documento.
"""
import uuid
from dataclasses import dataclass, field

from app.pipeline.segmenter import PageAnalysis, clean_region, normalize_number, verify_type


@dataclass
class GroupedRegion:
    page_id: uuid.UUID
    index_on_page: int
    bbox: dict | None
    position_hint: str | None


@dataclass
class GroupedDocument:
    doc_type: str
    confidence: float
    evidence: str | None
    number_seen: str | None
    regions: list[GroupedRegion] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)


def _continues(document: GroupedDocument | None, doc_type: str, number: str | None) -> bool:
    if document is None or document.doc_type == "DESCONOCIDO":
        return False
    if doc_type not in (document.doc_type, "DESCONOCIDO"):
        return False
    previous, current = normalize_number(document.number_seen), normalize_number(number)
    return previous is None or current is None or previous == current


def group_pages(pages: list[tuple[uuid.UUID, PageAnalysis]]) -> list[GroupedDocument]:
    """`pages`: las páginas de UN archivo, en orden, con la respuesta del segmentador."""
    documents: list[GroupedDocument] = []
    last: GroupedDocument | None = None  # último documento de la página anterior

    for page_id, analysis in pages:
        detected = sorted(analysis.documents, key=lambda d: d.index)
        last_on_page: GroupedDocument | None = None
        for position, doc in enumerate(detected, start=1):
            bbox, region_issues = clean_region(doc.region, len(detected))
            region = GroupedRegion(page_id, position, bbox, doc.position_hint)

            # Solo el primer documento de una página puede continuar el de la página anterior
            if doc.continuation_of_previous and position == 1 and _continues(last, doc.doc_type, doc.document_number_seen):
                last.regions.append(region)
                last.issues.extend(region_issues)
                last.number_seen = last.number_seen or doc.document_number_seen
                last_on_page = last
                continue

            doc_type, issues = verify_type(doc.doc_type, doc.evidence, doc.confidence)
            if doc.continuation_of_previous:
                issues.append(
                    {
                        "code": "AGRUPACION_DUDOSA",
                        "severity": "ADVERTENCIA",
                        "message": "La IA lo marcó como continuación del documento anterior, pero no coincide "
                        "(tipo, número o posición); se registró como documento aparte.",
                        "details": {"number_seen": doc.document_number_seen},
                    }
                )
            if analysis.page_quality.level == "BAJA":
                issues.append(
                    {
                        "code": "BAJA_CALIDAD_IMAGEN",
                        "severity": "ADVERTENCIA",
                        "message": "Imagen de baja calidad: " + (", ".join(analysis.page_quality.issues) or "sin detalle"),
                        "details": {"issues": analysis.page_quality.issues},
                    }
                )
            current = GroupedDocument(
                doc_type=doc_type,
                confidence=doc.confidence,
                evidence=doc.evidence,
                number_seen=doc.document_number_seen,
                regions=[region],
                issues=issues + region_issues,
            )
            documents.append(current)
            last_on_page = current
        last = last_on_page
    return documents
