"""Piezas comunes de los modelos."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field


def utcnow() -> datetime:
    return datetime.now(UTC)


def uuid_pk():
    """UUID como clave primaria: no permite adivinar otros registros cambiando un número en la URL."""
    return Field(default_factory=uuid.uuid4, primary_key=True)


def timestamp(*, default_now: bool = True):
    """Fecha y hora con zona horaria (timestamptz). Sin default_now, es opcional y empieza vacía."""
    if default_now:
        return Field(
            default_factory=utcnow,
            sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
        )
    return Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
