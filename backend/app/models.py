"""Las tablas de la base, tal como están definidas en db/*.sql (la fuente de verdad).

Estas clases solo sirven para leer y escribir desde Python: las tablas, sus reglas (CHECK) y los
índices se crean con los archivos SQL, nunca desde aquí.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, Column, Computed, Text
from sqlmodel import Field, SQLModel


# Rol del usuario que representa a la IA (db/005): sus documentos no los revisó una persona
MODEL_ROLE = "MODELO"


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
    imagen: str  # nombre del archivo del documento: TIPO_RUT_FOLIO.ext (en documentos/ del almacenamiento)
    # El "Modelo IA" si lo procesó la IA; la persona que lo corrigió, si alguien intervino
    id_usuario: int = Field(foreign_key="usuarios.id")
    # Nombres de columna de los campos con problemas: no se leyeron / se leyeron sin seguridad
    campos_faltantes: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text), nullable=False))
    campos_dudosos: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(Text), nullable=False))
    revisado_en: datetime | None = None  # cuándo lo revisó una persona
    creado_en: datetime | None = Field(default=None, sa_column_kwargs={"server_default": "now()"})
    # La calcula la base: nunca se escribe desde aquí
    requiere_revision: bool | None = Field(
        default=None,
        sa_column=Column(
            Boolean, Computed("observaciones <> 'LEGIBLE' AND revisado_en IS NULL", persisted=True)
        ),
    )


class LlamadaIA(SQLModel, table=True):
    """Una solicitud pagada a la IA (db/007): tokens, costo estimado y espera, para las métricas."""

    __tablename__ = "llamadas_ia"

    id: int | None = Field(default=None, primary_key=True)
    creado_en: datetime | None = Field(default=None, sa_column_kwargs={"server_default": "now()"})
    etapa: str  # CLASIFICACION, LECTURA_1 o LECTURA_2
    modelo: str
    id_tanda: str | None = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    costo_usd: Decimal = Decimal(0)
    espera_s: Decimal | None = None
    resultado: str  # OK, ERROR, RECHAZO o FORMATO
    id_documento: int | None = Field(default=None, foreign_key="documentos_procesados.id")
