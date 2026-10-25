"""Consulta de documentos_procesados y de los tipos de documento."""
from datetime import date, datetime
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import DocumentoProcesado, TipoDocumento
from app.storage import get_storage

router = APIRouter(tags=["documentos"])

MEDIA_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}


class TipoDocumentoRead(BaseModel):
    id: int
    documento: str
    descripcion: str


class DocumentoRead(BaseModel):
    id: int
    tipo: str  # FC, CI o GD
    rut_proveedor: str | None
    folio: str | None
    fecha: date | None
    firma: bool
    impuestos: int | None
    total_neto: int | None
    iva: int | None
    total: int | None
    observaciones: str
    requiere_revision: bool
    imagen: str
    creado_en: datetime


class DocumentoPage(BaseModel):
    total: int
    documentos: list[DocumentoRead]


class Resumen(BaseModel):
    total: int
    requieren_revision: int
    por_observaciones: dict[str, int]
    por_tipo: dict[str, int]


def _read(row: DocumentoProcesado, tipo: str) -> DocumentoRead:
    return DocumentoRead(tipo=tipo, **row.model_dump(exclude={"id_tipo_documento"}))


@router.get("/tipos-documentos", response_model=list[TipoDocumentoRead])
def list_types(session: SessionDep):
    return session.exec(select(TipoDocumento).order_by(col(TipoDocumento.id))).all()


@router.get("/documentos", response_model=DocumentoPage)
def list_documents(
    session: SessionDep,
    tipo: str | None = Query(None, description="FC, CI o GD"),
    observaciones: str | None = Query(None, description="LEGIBLE, NO_LEGIBLE o DESCUADRE"),
    requiere_revision: bool | None = None,
    q: str | None = Query(None, description="Busca en RUT y folio"),
    limite: int = Query(50, ge=1, le=500),
    desde: int = Query(0, ge=0),
):
    """Los más recientes primero."""
    query = select(DocumentoProcesado, TipoDocumento.documento).join(
        TipoDocumento, col(TipoDocumento.id) == DocumentoProcesado.id_tipo_documento
    )
    if tipo:
        query = query.where(TipoDocumento.documento == tipo.upper())
    if observaciones:
        query = query.where(DocumentoProcesado.observaciones == observaciones.upper())
    if requiere_revision is not None:
        query = query.where(DocumentoProcesado.requiere_revision == requiere_revision)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(col(DocumentoProcesado.folio).ilike(term), col(DocumentoProcesado.rut_proveedor).ilike(term)))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    rows = session.exec(
        query.order_by(col(DocumentoProcesado.creado_en).desc(), col(DocumentoProcesado.id).desc()).offset(desde).limit(limite)
    ).all()
    return DocumentoPage(total=total, documentos=[_read(row, code) for row, code in rows])


@router.get("/documentos/resumen", response_model=Resumen)
def summary(session: SessionDep):
    by_observation = dict(
        session.exec(
            select(DocumentoProcesado.observaciones, func.count()).group_by(DocumentoProcesado.observaciones)
        ).all()
    )
    by_type = dict(
        session.exec(
            select(TipoDocumento.documento, func.count())
            .join(DocumentoProcesado, col(DocumentoProcesado.id_tipo_documento) == TipoDocumento.id)
            .group_by(TipoDocumento.documento)
        ).all()
    )
    total = sum(by_observation.values())
    return Resumen(
        total=total,
        requieren_revision=total - by_observation.get("LEGIBLE", 0),
        por_observaciones=by_observation,
        por_tipo=by_type,
    )


def _get(session: SessionDep, documento_id: int) -> tuple[DocumentoProcesado, str]:
    found = session.exec(
        select(DocumentoProcesado, TipoDocumento.documento)
        .join(TipoDocumento, col(TipoDocumento.id) == DocumentoProcesado.id_tipo_documento)
        .where(DocumentoProcesado.id == documento_id)
    ).first()
    if found is None:
        raise HTTPException(404, "Documento no encontrado")
    return found


@router.get("/documentos/{documento_id}", response_model=DocumentoRead)
def get_document(documento_id: int, session: SessionDep):
    row, code = _get(session, documento_id)
    return _read(row, code)


@router.get("/documentos/{documento_id}/imagen")
def get_image(documento_id: int, session: SessionDep):
    """El archivo original (imagen o PDF) del que salió el documento."""
    row, _ = _get(session, documento_id)
    storage = get_storage()
    if not storage.exists(row.imagen):
        raise HTTPException(404, "El archivo original ya no está en el almacenamiento")
    media_type = MEDIA_TYPES.get(PurePosixPath(row.imagen).suffix, "application/octet-stream")
    return Response(storage.get(row.imagen), media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})
