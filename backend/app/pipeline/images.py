"""Nombre de la imagen de cada documento: TIPO_RUT_FOLIO (por ejemplo FC_93178000-K_23193169.png).

- Se arma con los datos ya extraídos (o corregidos por una persona). Lo que falta queda vacío: un RUT
  ilegible se omite (nunca va "1-9"): FC__1458754. Sin folio: FC_93178000-K_.
- El archivo original se copia con ese nombre en documentos/ y la columna imagen guarda el nombre.
  Si una foto trae dos documentos, hay una copia por documento.
- Si el nombre ya lo usa otro documento, se agrega -2, -3…: nunca se sobrescribe otra imagen.
"""
from pathlib import PurePosixPath

from sqlmodel import Session, select

from app.models import DocumentoProcesado
from app.pipeline.fields import SUBSTITUTE_RUT
from app.storage import document_key, get_storage


def base_name(type_code: str, rut: str | None, folio: str | None) -> str:
    rut = "" if rut in (None, SUBSTITUTE_RUT) else rut
    return f"{type_code}_{rut}_{folio or ''}"


def free_name(session: Session, base: str, extension: str, document_id: int | None = None) -> str:
    """El nombre con extensión, sin repetir el de otro documento (se agrega -2, -3…)."""
    number = 1
    # Sin autoflush: la consulta no debe guardar antes de tiempo cambios pendientes de la fila
    with session.no_autoflush:
        while True:
            name = f"{base}{'' if number == 1 else f'-{number}'}{extension}"
            taken = session.exec(
                select(DocumentoProcesado.id).where(
                    DocumentoProcesado.imagen == name, DocumentoProcesado.id != (document_id or 0)
                )
            ).first()
            if taken is None:
                return name
            number += 1


def store_copy(source_key: str, name: str) -> None:
    """Copia el archivo con su nombre de documento."""
    storage = get_storage()
    storage.put(document_key(name), storage.get(source_key))


def rename(session: Session, row: DocumentoProcesado, type_code: str) -> str | None:
    """Tras corregir tipo, RUT o folio: copia la imagen con el nombre nuevo. Devuelve el nombre anterior
    (para borrarlo después de guardar) o None si no cambió."""
    extension = PurePosixPath(row.imagen).suffix
    name = free_name(session, base_name(type_code, row.rut_proveedor, row.folio), extension, row.id)
    if name == row.imagen:
        return None
    old = row.imagen
    store_copy(document_key(old), name)
    row.imagen = name
    return old
