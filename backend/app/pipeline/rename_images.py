"""Pone el nombre TIPO_RUT_FOLIO a los documentos guardados antes de que existiera (una sola vez).

    python -m app.pipeline.rename_images

Los documentos cuya columna imagen todavía es la ubicación del original (originals/…) reciben una copia
con su nombre en documentos/. El original no se borra. Se puede ejecutar más de una vez.
"""
from pathlib import PurePosixPath

from sqlmodel import Session, col, select

from app.db.session import engine
from app.models import DocumentoProcesado, TipoDocumento
from app.pipeline import images
from app.storage import get_storage


def main() -> None:
    storage = get_storage()
    with Session(engine) as session:
        rows = session.exec(
            select(DocumentoProcesado, TipoDocumento.documento)
            .join(TipoDocumento, col(TipoDocumento.id) == DocumentoProcesado.id_tipo_documento)
            .where(col(DocumentoProcesado.imagen).startswith("originals/"))
            .order_by(col(DocumentoProcesado.id))
        ).all()
        for row, code in rows:
            if not storage.exists(row.imagen):
                print(f"  ✖ documento {row.id}: falta el original {row.imagen}")
                continue
            base = images.base_name(code, row.rut_proveedor, row.folio)
            name = images.free_name(session, base, PurePosixPath(row.imagen).suffix, row.id)
            images.store_copy(row.imagen, name)
            print(f"  documento {row.id}: {row.imagen} → {name}")
            row.imagen = name
            session.add(row)
            session.commit()
    print(f"Listo: {len(rows)} documento(s) revisado(s).")


if __name__ == "__main__":
    main()
