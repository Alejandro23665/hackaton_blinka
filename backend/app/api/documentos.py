"""Consulta y corrección de documentos_procesados, totales del día, carpetas y tipos de documento."""
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import Date, case, cast, func, literal, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.auth import CurrentUser
from app.core.config import settings
from app.models import Carpeta, DocumentoProcesado, TipoDocumento, Usuario
from app.pipeline import images
from app.pipeline.normalize import parse_document_number, parse_rut
from app.storage import document_key, get_storage

router = APIRouter(tags=["documentos"])

MEDIA_TYPES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}


class TipoDocumentoRead(BaseModel):
    id: int
    documento: str


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
    campos_faltantes: list[str]
    campos_dudosos: list[str]
    imagen: str
    id_usuario: int
    usuario: str  # "Modelo IA" o la persona que lo corrigió
    revisado_en: datetime | None
    creado_en: datetime
    id_carpeta: int | None
    carpeta: str | None  # nombre de la carpeta subida; vacío si se subió suelto


class CarpetaRead(BaseModel):
    id: int
    nombre: str
    subida_en: datetime
    usuario: str  # quién la subió
    documentos: int  # documentos guardados de esta carpeta
    requieren_revision: int


class DocumentoPage(BaseModel):
    total: int
    documentos: list[DocumentoRead]


class Resumen(BaseModel):
    total: int
    requieren_revision: int
    por_observaciones: dict[str, int]
    por_tipo: dict[str, int]


class Dia(BaseModel):
    fecha: date
    registrados: int  # documentos guardados ese día
    procesados_ia: int  # legibles sin intervención de una persona
    requieren_revision: int  # pendientes de revisión humana
    revisados: int  # corregidos o confirmados por una persona
    pendientes_total: int  # pendientes de revisión de todos los días


class Correccion(BaseModel):
    """Los datos que confirma o corrige una persona."""

    tipo: Literal["FC", "CI", "GD"]
    rut_proveedor: str
    folio: str = Field(min_length=1, max_length=20)
    fecha: date
    firma: bool
    total_neto: int | None = Field(None, ge=0)
    iva: int | None = Field(None, ge=0)
    impuestos: int | None = Field(None, ge=0)
    total: int | None = Field(None, ge=0)
    # Si los montos no cuadran, la persona confirma que el documento trae ese descuadre
    confirmar_descuadre: bool = False


def _query():
    return (
        select(DocumentoProcesado, TipoDocumento.documento, Usuario.nombre, Carpeta.nombre)
        .join(TipoDocumento, col(TipoDocumento.id) == DocumentoProcesado.id_tipo_documento)
        .join(Usuario, col(Usuario.id) == DocumentoProcesado.id_usuario)
        .outerjoin(Carpeta, col(Carpeta.id) == DocumentoProcesado.id_carpeta)
    )


def _read(row: DocumentoProcesado, tipo: str, usuario: str, carpeta: str | None) -> DocumentoRead:
    return DocumentoRead(tipo=tipo, usuario=usuario, carpeta=carpeta, **row.model_dump(exclude={"id_tipo_documento"}))


def _local_day(column):
    """Fecha de un instante en la zona horaria del negocio (por defecto, Chile)."""
    return cast(func.timezone(settings.TIMEZONE, column), Date)


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
    carpeta: int | None = Query(None, description="Id de la carpeta subida"),
    orden: Literal["recientes", "antiguos"] = "recientes",
    limite: int = Query(50, ge=1, le=500),
    desde: int = Query(0, ge=0),
):
    """Por defecto los más recientes primero; la cola de revisión usa los más antiguos primero."""
    query = _query()
    if tipo:
        query = query.where(TipoDocumento.documento == tipo.upper())
    if observaciones:
        query = query.where(DocumentoProcesado.observaciones == observaciones.upper())
    if requiere_revision is not None:
        query = query.where(DocumentoProcesado.requiere_revision == requiere_revision)
    if carpeta is not None:
        query = query.where(DocumentoProcesado.id_carpeta == carpeta)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.where(or_(col(DocumentoProcesado.folio).ilike(term), col(DocumentoProcesado.rut_proveedor).ilike(term)))
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    order = (col(DocumentoProcesado.creado_en), col(DocumentoProcesado.id))
    if orden == "recientes":
        order = tuple(c.desc() for c in order)
    rows = session.exec(query.order_by(*order).offset(desde).limit(limite)).all()
    return DocumentoPage(total=total, documentos=[_read(*row) for row in rows])


@router.get("/carpetas", response_model=list[CarpetaRead])
def list_folders(session: SessionDep, limite: int = Query(100, ge=1, le=500)):
    """Las carpetas subidas, la más reciente primero, con cuántos documentos se guardaron de cada una."""
    documents = func.count(DocumentoProcesado.id)
    pending = func.count(DocumentoProcesado.id).filter(DocumentoProcesado.requiere_revision)
    rows = session.exec(
        select(Carpeta, Usuario.nombre, documents, pending)
        .join(Usuario, col(Usuario.id) == Carpeta.id_usuario)
        .outerjoin(DocumentoProcesado, col(DocumentoProcesado.id_carpeta) == Carpeta.id)
        .group_by(col(Carpeta.id), col(Usuario.nombre))
        .order_by(col(Carpeta.subida_en).desc(), col(Carpeta.id).desc())
        .limit(limite)
    ).all()
    return [
        CarpetaRead(id=f.id, nombre=f.nombre, subida_en=f.subida_en, usuario=user, documentos=n, requieren_revision=p)
        for f, user, n, p in rows
    ]


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
    pending = session.exec(select(func.count()).where(col(DocumentoProcesado.requiere_revision))).one()
    return Resumen(
        total=sum(by_observation.values()),
        requieren_revision=pending,
        por_observaciones=by_observation,
        por_tipo=by_type,
    )


@router.get("/documentos/dia", response_model=Dia)
def day(session: SessionDep, fecha: date | None = Query(None, description="Por defecto, hoy")):
    """Totales de los documentos registrados en un día (zona horaria TIMEZONE)."""
    day_value = fecha or session.exec(select(_local_day(func.now()))).one()

    def count(condition):
        return func.count(case((condition, literal(1))))

    reviewed = col(DocumentoProcesado.revisado_en).is_not(None)
    registered, by_ai, pending, by_person = session.exec(
        select(
            func.count(),
            count((DocumentoProcesado.observaciones == "LEGIBLE") & ~reviewed),
            count(col(DocumentoProcesado.requiere_revision)),
            count(reviewed),
        ).where(_local_day(col(DocumentoProcesado.creado_en)) == day_value)
    ).one()
    pending_total = session.exec(select(func.count()).where(col(DocumentoProcesado.requiere_revision))).one()
    return Dia(
        fecha=day_value,
        registrados=registered,
        procesados_ia=by_ai,
        requieren_revision=pending,
        revisados=by_person,
        pendientes_total=pending_total,
    )


def _get(session: SessionDep, documento_id: int) -> tuple[DocumentoProcesado, str, str, str | None]:
    found = session.exec(_query().where(DocumentoProcesado.id == documento_id)).first()
    if found is None:
        raise HTTPException(404, "Documento no encontrado")
    return found


@router.get("/documentos/{documento_id}", response_model=DocumentoRead)
def get_document(documento_id: int, session: SessionDep):
    return _read(*_get(session, documento_id))


@router.put("/documentos/{documento_id}/correccion", response_model=DocumentoRead)
def correct(documento_id: int, data: Correccion, session: SessionDep, user: CurrentUser):
    """Una persona corrige o confirma los datos. Queda a su nombre y sale de la cola de revisión.

    Se aplican las mismas reglas que al procesar: RUT con dígito verificador correcto y
    neto + IVA + impuestos = total. Si no cuadra, solo se guarda si la persona confirma el descuadre.
    """
    row, *_ = _get(session, documento_id)
    rut = parse_rut(data.rut_proveedor)
    if rut.value is None:
        raise HTTPException(422, f"RUT no válido: {rut.reason}")
    folio = parse_document_number(data.folio)
    if folio.value is None:
        raise HTTPException(422, f"Folio no válido: {folio.reason}")

    amounts = (data.total_neto, data.iva, data.impuestos, data.total)
    unvalued_guide = data.tipo == "GD" and all(a is None for a in amounts)
    if unvalued_guide:
        observations = "LEGIBLE"
    else:
        missing = [name for name in ("total_neto", "iva", "total") if getattr(data, name) is None]
        if missing:
            raise HTTPException(422, "Faltan montos obligatorios: " + ", ".join(missing))
        difference = data.total - (data.total_neto + data.iva + (data.impuestos or 0))
        observations = "LEGIBLE"
        if abs(Decimal(difference)) > settings.TOTAL_TOLERANCE_CLP:
            if not data.confirmar_descuadre:
                raise HTTPException(
                    422,
                    f"Neto + IVA + impuestos no da el total (diferencia {difference}). "
                    "Revisa los montos o confirma que el documento trae ese descuadre.",
                )
            observations = "DESCUADRE"

    type_id = session.exec(select(TipoDocumento.id).where(TipoDocumento.documento == data.tipo)).one()
    row.id_tipo_documento = type_id
    row.rut_proveedor = rut.value
    row.folio = folio.value
    row.fecha = data.fecha
    row.firma = data.firma
    row.total_neto, row.iva, row.impuestos, row.total = amounts
    row.observaciones = observations
    row.id_usuario = user.id
    row.revisado_en = datetime.now(timezone.utc)
    # Con tipo, RUT o folio corregidos, la imagen toma el nombre nuevo (TIPO_RUT_FOLIO)
    old_image = images.rename(session, row, data.tipo)
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if old_image:
            get_storage().delete(document_key(row.imagen))
        if "uq_documentos_procesados_documento" in str(exc):
            raise HTTPException(409, "Ya hay otro documento guardado con ese tipo, RUT y folio.") from exc
        raise
    if old_image:
        get_storage().delete(document_key(old_image))
    return _read(*_get(session, documento_id))


@router.get("/documentos/{documento_id}/imagen")
def get_image(documento_id: int, session: SessionDep):
    """El archivo (imagen o PDF) del que salió el documento, con su nombre TIPO_RUT_FOLIO."""
    row, *_ = _get(session, documento_id)
    storage = get_storage()
    key = document_key(row.imagen)
    if not storage.exists(key):
        raise HTTPException(404, "El archivo ya no está en el almacenamiento")
    media_type = MEDIA_TYPES.get(PurePosixPath(row.imagen).suffix, "application/octet-stream")
    headers = {"Cache-Control": "private, no-cache", "Content-Disposition": f'inline; filename="{row.imagen}"'}
    return Response(storage.get(key), media_type=media_type, headers=headers)
