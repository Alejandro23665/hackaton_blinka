from sqlalchemy import Column, ForeignKey, Integer, LargeBinary
from sqlmodel import Field, SQLModel


class DocumentFile(SQLModel, table=True):
    """Contenido del archivo subido, en una tabla aparte.

    Se guarda en Postgres (no en disco) para que el despliegue no dependa de un disco persistente,
    y en su propia tabla para que listar documentos no cargue varios MB por fila.
    """

    __tablename__ = "document_files"

    document_id: int = Field(
        sa_column=Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    )
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
