"""Evaluación con muestras reales.

    python -m app.evaluation.run                  # procesa las muestras pendientes y genera el informe
    python -m app.evaluation.run --solo-informe   # solo compara (no llama a la IA)
    python -m app.evaluation.run --limite 10      # procesa como mucho 10 imágenes nuevas

- Usa una base aparte (<tu base>_eval_docs) y un almacenamiento aparte (backend/storage_eval): no se
  mezcla con tus datos. La caché de la IA sí se comparte: repetir no gasta cuota.
- Cada imagen se sube como un lote. Si se agota la cuota, se detiene; al volver a ejecutarlo
  retoma donde quedó sin repetir lo hecho.
- muestras/respuestas.json: las respuestas correctas. Las imágenes nuevas se agregan prellenadas
  con lo que leyó el sistema y "revisado": false; se corrigen a mano y se marcan "revisado": true.
  Solo las revisadas cuentan en el informe.
- muestras/resultados/: lo que leyó el sistema (sistema.json) y el informe (informe.md).
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, col, select

import app.models  # noqa: F401  (registra las tablas)
from app.core.config import BACKEND_DIR, settings
from app.evaluation.compare import compare, report
from app.models import PageClassification, Page, ProcessingRun, StoredFile, SubmissionFile
from app.pipeline import intake
from app.pipeline.orchestrator import file_documents, process_submission

SAMPLES = BACKEND_DIR.parent / "muestras"
IMAGES = SAMPLES / "imagenes"
ANSWERS = SAMPLES / "respuestas.json"
RESULTS = SAMPLES / "resultados"
QUOTA_MARKERS = ("CUOTA", "límite diario")


def _eval_engine():
    """Base <nombre>_eval_docs en el mismo servidor; se crea si no existe (no toca la _eval de Rekreuz)."""
    url = make_url(settings.DATABASE_URL)
    name = f"{url.database}_eval_docs"
    admin = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f'CREATE DATABASE "{name}"')
    engine = create_engine(url.set(database=name))
    SQLModel.metadata.create_all(engine)
    return engine


def _images() -> list[Path]:
    files = [p for p in IMAGES.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".pdf")]
    return sorted(files, key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.name)])


def _stored(session: Session, data: bytes) -> StoredFile | None:
    return session.exec(select(StoredFile).where(StoredFile.sha256 == hashlib.sha256(data).hexdigest())).first()


def _quota_hit(session: Session, stored: StoredFile) -> bool:
    pages = [p.id for p in session.exec(select(Page).where(Page.file_id == stored.id)).all()]
    errors = session.exec(
        select(PageClassification.error).where(col(PageClassification.page_id).in_(pages), PageClassification.status == "ERROR")
    ).all()
    codes = [run.error_code or "" for doc, _ in file_documents(session, stored) for run in _runs(session, doc.id)]
    return any(m in (e or "") for e in errors for m in QUOTA_MARKERS) or "CUOTA" in codes or "CLAVE" in codes


def _runs(session: Session, document_id) -> list[ProcessingRun]:
    return list(session.exec(select(ProcessingRun).where(ProcessingRun.document_id == document_id)).all())


def _done(session: Session, stored: StoredFile | None) -> bool:
    if stored is None or stored.preprocess_status != "LISTO":
        return False
    documents = file_documents(session, stored)
    return bool(documents) and all(
        any(r.technical_status == "COMPLETADO" for r in _runs(session, doc.id)) for doc, _ in documents
    )


def _shown(runs: list[ProcessingRun]) -> ProcessingRun | None:
    current = [r for r in runs if r.is_current]
    return current[0] if current else (max(runs, key=lambda r: r.run_number) if runs else None)


def _number(value):
    return None if value is None else (int(value) if value == value.to_integral_value() else float(value))


def _summary(session: Session, stored: StoredFile) -> dict:
    documents = []
    for doc, _ in file_documents(session, stored):
        run = _shown(_runs(session, doc.id))
        if run is None:
            continue
        documents.append(
            {
                "tipo": run.doc_type,
                "estado": run.overall_status or run.technical_status,
                "rut": None if run.rut_is_substitute else run.provider_rut,
                "numero": run.document_number,
                "fecha": run.issue_date.isoformat() if run.issue_date else None,
                "neto": _number(run.net_amount),
                "iva": _number(run.vat_amount),
                "otros_impuestos": _number(run.other_taxes_amount),
                "exento": _number(run.exempt_amount),
                "total": _number(run.total_amount),
                "firma": run.has_signature,
            }
        )
    return {"documentos": documents}


def process(engine, limit: int | None) -> dict[str, dict]:
    """Procesa las imágenes pendientes. Devuelve lo que leyó el sistema en cada una."""
    system: dict[str, dict] = {}
    new = 0
    for path in _images():
        data = path.read_bytes()
        with Session(engine) as session:
            stored = _stored(session, data)
            if not _done(session, stored):
                if limit is not None and new >= limit:
                    continue
                new += 1
                print(f"→ {path.name} …", flush=True)
                if stored is None:
                    received = intake.receive(session, [intake.Upload(path.name, data)])
                    submission_id = received.submission.id
                else:
                    submission_id = session.exec(
                        select(SubmissionFile.submission_id).where(SubmissionFile.file_id == stored.id)
                    ).first()
                process_submission(engine, submission_id)
                session.expire_all()
                stored = _stored(session, data)
                if _quota_hit(session, stored):
                    print("  ✖ Se agotó la cuota de la IA (o la clave fue rechazada). Vuelve a ejecutarlo más tarde.")
                    system[path.name] = _summary(session, stored)
                    break
            if stored is not None and _done(session, stored):
                system[path.name] = _summary(session, stored)
                docs = system[path.name]["documentos"]
                print(f"  {path.name}: " + "; ".join(f"{d['tipo']} {d['estado']}" for d in docs), flush=True)
    return system


def _load_answers() -> list[dict]:
    if ANSWERS.is_file():
        return json.loads(ANSWERS.read_text(encoding="utf-8"))
    return []


def _save_answers(answers: list[dict], system: dict[str, dict]) -> int:
    """Agrega, prellenadas con lo que leyó el sistema, las imágenes que aún no tienen respuesta."""
    known = {a["archivo"] for a in answers}
    added = 0
    for name in [p.name for p in _images()]:
        if name in known or name not in system:
            continue
        answers.append({"archivo": name, "revisado": False, **system[name]})
        added += 1
    order = {p.name: i for i, p in enumerate(_images())}
    answers.sort(key=lambda a: order.get(a["archivo"], 10**6))
    ANSWERS.write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limite", type=int, default=None, help="Máximo de imágenes nuevas a procesar")
    parser.add_argument("--solo-informe", action="store_true", help="No procesa; solo compara lo ya leído")
    args = parser.parse_args()

    if not IMAGES.is_dir():
        sys.exit(f"No existe {IMAGES}: copia ahí las imágenes de muestra.")
    settings.STORAGE_DIR = BACKEND_DIR / "storage_eval"
    engine = _eval_engine()
    RESULTS.mkdir(parents=True, exist_ok=True)

    if args.solo_informe:
        system = json.loads((RESULTS / "sistema.json").read_text(encoding="utf-8"))
    else:
        system = process(engine, args.limite)
        previous = RESULTS / "sistema.json"
        if previous.is_file():
            system = {**json.loads(previous.read_text(encoding="utf-8")), **system}
        (RESULTS / "sistema.json").write_text(json.dumps(system, ensure_ascii=False, indent=2), encoding="utf-8")

    answers = _load_answers()
    added = _save_answers(answers, system)
    reviewed = [a for a in answers if a.get("revisado")]
    totals = compare(reviewed, system)
    text = report(totals, pending=len(answers) - len(reviewed))
    (RESULTS / "informe.md").write_text(text, encoding="utf-8")

    total_images = len(_images())
    print(f"\nProcesadas: {len(system)} de {total_images} imágenes. Respuestas nuevas por revisar: {added}.")
    print(f"Revisadas: {len(reviewed)}. Informe: {RESULTS / 'informe.md'}")


if __name__ == "__main__":
    main()
