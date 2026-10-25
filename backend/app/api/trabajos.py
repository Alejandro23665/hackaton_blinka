"""Subida de archivos y avance de su procesamiento (en memoria, ver app/pipeline/jobs.py)."""
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.api.deps import EngineDep
from app.pipeline import jobs

router = APIRouter(prefix="/trabajos", tags=["trabajos"])


@router.post("", status_code=202)
async def create(background: BackgroundTasks, engine: EngineDep, files: list[UploadFile] = File(...)) -> dict:
    """Recibe imágenes o PDF y los procesa en segundo plano. Responde enseguida con el trabajo."""
    uploads = [jobs.Upload(name=f.filename or "archivo", data=await f.read()) for f in files]
    try:
        job = jobs.create_job(uploads)
    except jobs.InvalidUpload as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    background.add_task(jobs.run_job, engine, job.id)
    return job.to_dict()


@router.get("")
def list_all() -> list[dict]:
    """Los trabajos recientes (desde que arrancó el servidor), el más nuevo primero."""
    return [job.to_dict() for job in jobs.list_jobs()]


@router.get("/{job_id}")
def get(job_id: str) -> dict:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Trabajo no encontrado (el servidor se reinició o es muy antiguo)")
    return job.to_dict()
