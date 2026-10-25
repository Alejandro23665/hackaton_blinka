"""Las 4 tablas de la base, tal como están definidas en db/*.sql (la fuente de verdad).

Estas clases solo sirven para leer y escribir desde Python: las tablas, sus reglas (CHECK) y los
índices se crean con los archivos SQL, nunca desde aquí.
"""
from datetime import date, datetime

from sqlalchemy import Boolean, Column, Computed
from sqlmodel import Field, SQLModel


class Rol(SQLModel, table=True):
    __tablename__ = "roles"

    id: int | None = Field(default=None, primary_key=True)
    rol: str
    creado_en: datetime | None = Field(default=None, sa_column_kwargs={"server_default": "now()"})


class Usuario(SQLModel, table=True):
    __tablename__ = "usuarios"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str
    email: str
    contrasena_hash: str
    id_rol: int = Field(foreign_key="roles.id")
    creado_en: datetime | None = Field(default=None, sa_column_kwargs={"server_default": "now()"})


class TipoDocumento(SQLModel, table=True):
    __tablename__ = "tipos_documentos"

    id: int | None = Field(default=None, primary_key=True)
    documento: str  # FC, CI o GD
    descripcion: str


class DocumentoProcesado(SQLModel, table=True):
    __tablename__ = "documentos_procesados"

    id: int | None = Field(default=None, primary_key=True)
    rut_proveedor: str | None = None
    folio: str | None = None
    fecha: date | None = None
    firma: bool = False
    impuestos: int | None = None  # otros impuestos + exento (el IVA va aparte)
    total_neto: int | None = None
    iva: int | None = None
    total: int | None = None
    observaciones: str  # LEGIBLE, NO_LEGIBLE o DESCUADRE
    id_tipo_documento: int = Field(foreign_key="tipos_documentos.id")
    imagen: str  # clave del archivo original en el almacenamiento
    creado_en: datetime | None = Field(default=None, sa_column_kwargs={"server_default": "now()"})
    # La calcula la base (observaciones <> 'LEGIBLE'): nunca se escribe desde aquí
    requiere_revision: bool | None = Field(
        default=None, sa_column=Column(Boolean, Computed("observaciones <> 'LEGIBLE'", persisted=True))
    )
