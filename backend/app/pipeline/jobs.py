"""Trabajos de procesamiento, con su avance en memoria (no en la base).

Una subida de archivos es un trabajo: se validan y se guardan los originales al recibirlos, y se
procesan después, todos juntos (sus llamadas a la IA van en las mismas tandas). La pantalla consulta
el avance mientras tanto, con la etapa en que está.

- Los trabajos se procesan de a uno (cola).
- Si el servidor se reinicia, el avance se pierde; los documentos ya guardados quedan en la base.
- Se recuerdan los últimos MAX_JOBS trabajos.
"""
import hashlib
import logging
import threading
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.core.config import settings
from app.pipeline.preprocess import detect_type
from app.pipeline.process import AIUnavailable, DocumentResult, FileInput, process_files
from app.storage import get_storage, original_key

MAX_JOBS = 100

logger = logging.getLogger(__name__)


class InvalidUpload(ValueError):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Upload:
    name: str
    data: bytes


@dataclass
class JobFile:
    nombre: str
    imagen: str  # clave del original en el almacenamiento
    tipo_contenido: str
    estado: str = "PENDIENTE"  # PENDIENTE, EN_PROCESO, TERMINADO, ERROR u OMITIDO
    mensaje: str | None = None
    documentos: list[DocumentResult] = field(default_factory=list)


@dataclass
class Job:
    id: str
    creado_en: datetime
    archivos: list[JobFile]
    estado: str = "EN_COLA"  # EN_COLA, EN_PROCESO, TERMINADO o DETENIDO
    mensaje: str | None = None
    # Qué está haciendo ahora, por ejemplo "Leyendo documentos. Esperando a Claude…"
    etapa: str | None = None
    etapa_desde: datetime | None = None

    def to_dict(self) -> dict:
        return asdict(self)


_jobs: "OrderedDict[str, Job]" = OrderedDict()
_jobs_lock = threading.Lock()
# Un trabajo a la vez
_run_lock = threading.Lock()


def _validate(uploads: list[Upload]) -> list[tuple[Upload, str, str, str]]:
    """Comprueba todo antes de guardar nada: un archivo inválido rechaza la subida entera."""
    if not uploads:
        raise InvalidUpload("No se recibió ningún archivo", 422)
    if len(uploads) > settings.MAX_FILES_PER_SUBMISSION:
        raise InvalidUpload(f"Máximo {settings.MAX_FILES_PER_SUBMISSION} archivos por subida", 422)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    checked = []
    for upload in uploads:
        if not upload.data:
            raise InvalidUpload(f"'{upload.name}' está vacío", 422)
        if len(upload.data) > max_bytes:
            raise InvalidUpload(f"'{upload.name}' supera el máximo de {settings.MAX_UPLOAD_MB} MB", 413)
        try:
            content_type, extension = detect_type(upload.data)
        except ValueError as exc:
            raise InvalidUpload(f"'{upload.name}': {exc}", 415) from exc
        checked.append((upload, content_type, extension, hashlib.sha256(upload.data).hexdigest()))
    return checked


def create_job(uploads: list[Upload]) -> Job:
    """Valida y guarda los originales. El mismo archivo se guarda una sola vez (por su huella)."""
    storage = get_storage()
    files = []
    seen: set[str] = set()
    for upload, content_type, extension, sha in _validate(uploads):
        if sha in seen:
            continue
        seen.add(sha)
        key = original_key(sha, extension)
        if not storage.exists(key):
            storage.put(key, upload.data)
        files.append(JobFile(nombre=upload.name[:255], imagen=key, tipo_contenido=content_type))
    job = Job(id=uuid.uuid4().hex, creado_en=datetime.now(timezone.utc), archivos=files)
    with _jobs_lock:
        _jobs[job.id] = job
        while len(_jobs) > MAX_JOBS:
            _jobs.popitem(last=False)
    return job


def get_job(job_id: str) -> Job | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def list_jobs() -> list[Job]:
    with _jobs_lock:
        return list(reversed(_jobs.values()))


def run_job(engine: Engine, job_id: str) -> None:
    """Procesa los archivos del trabajo (en segundo plano). Si no se puede usar la IA, se detiene."""
    job = get_job(job_id)
    if job is None:
        return

    def progress(text: str) -> None:
        if text != job.etapa:
            job.etapa, job.etapa_desde = text, datetime.now(timezone.utc)

    with _run_lock:
        job.estado = "EN_PROCESO"
        for item in job.archivos:
            item.estado = "EN_PROCESO"
        files = [FileInput(item.imagen, item.tipo_contenido) for item in job.archivos]
        with Session(engine) as session:
            try:
                outcomes = process_files(session, files, progress)
            except AIUnavailable as exc:
                for item in job.archivos:
                    item.estado, item.mensaje = "ERROR", "No se procesó: la IA no está disponible."
                job.estado, job.mensaje = "DETENIDO", f"{exc} Vuelve a subir los archivos cuando esté resuelto."
                return
            except Exception as exc:  # error del propio código: se registra y se informa
                logger.exception("Error inesperado al procesar el trabajo %s", job.id)
                session.rollback()
                for item in job.archivos:
                    item.estado, item.mensaje = "ERROR", f"Error inesperado: {exc}"
                job.estado = "TERMINADO"
                return
            finally:
                job.etapa = job.etapa_desde = None
        for item, outcome in zip(job.archivos, outcomes):
            item.documentos = outcome.documentos
            item.estado, item.mensaje = ("ERROR", outcome.error) if outcome.error else ("TERMINADO", None)
        job.estado = "TERMINADO"
