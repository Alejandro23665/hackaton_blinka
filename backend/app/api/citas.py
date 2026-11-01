"""Citas: la página pública deja un email y un teléfono para agendar una cita (sin sesión), y un
administrador las ve en su panel."""
import re
import time
from collections import defaultdict, deque
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.models import Cita

# Sin sesión: cualquiera puede pedir una cita
public = APIRouter(tags=["citas"])
# Solo administradores (ver main.py)
router = APIRouter(prefix="/citas", tags=["citas"])

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Un número internacional tiene como mucho 15 dígitos en total (E.164), contando el prefijo
MAX_DIGITS = 15
# Freno al envío masivo: solicitudes por dirección IP en una ventana de tiempo
LIMIT, WINDOW_S = 5, 600
_recent: dict[str, deque[float]] = defaultdict(deque)


class CitaNueva(BaseModel):
    email: str = Field(max_length=255)
    pais: str = Field(pattern=r"^[A-Za-z]{2}$")
    prefijo: str = Field(pattern=r"^\+[0-9]{1,4}$")
    telefono: str = Field(max_length=30)
    # Campo trampa: invisible en el formulario. Si viene con algo, lo llenó un robot
    sitio_web: str = ""


class CitaRead(BaseModel):
    id: int
    email: str
    pais: str
    prefijo: str
    telefono: str
    creado_en: datetime


def _too_many(ip: str) -> bool:
    now = time.monotonic()
    times = _recent[ip]
    while times and now - times[0] > WINDOW_S:
        times.popleft()
    if len(times) >= LIMIT:
        return True
    times.append(now)
    return False


@public.post("/citas", status_code=201)
def request_appointment(data: CitaNueva, session: SessionDep, request: Request):
    """Registra una solicitud de cita. El teléfono llega sin el prefijo; se aceptan espacios y guiones."""
    email = data.email.strip()
    if not EMAIL.match(email):
        raise HTTPException(422, "Escribe un email válido.")
    phone = re.sub(r"[\s\-().]", "", data.telefono)
    if not phone.isdigit() or not 4 <= len(phone) <= MAX_DIGITS - (len(data.prefijo) - 1):
        raise HTTPException(422, "Escribe un número de teléfono válido, solo con dígitos.")
    if data.sitio_web:
        return {"ok": True}  # se responde igual para no darle pistas al robot
    if _too_many(request.client.host if request.client else ""):
        raise HTTPException(429, "Recibimos varias solicitudes seguidas. Inténtalo de nuevo en unos minutos.")
    session.add(Cita(email=email, pais=data.pais.upper(), prefijo=data.prefijo, telefono=phone))
    session.commit()
    return {"ok": True}


@router.get("", response_model=list[CitaRead])
def list_appointments(session: SessionDep):
    """Las solicitudes de cita, la más reciente primero."""
    return session.exec(select(Cita).order_by(col(Cita.creado_en).desc(), col(Cita.id).desc()).limit(500)).all()
