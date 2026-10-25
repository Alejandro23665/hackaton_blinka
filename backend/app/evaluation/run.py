"""Evaluación con muestras reales.

    python -m app.evaluation.run                  # procesa las muestras pendientes y genera el informe
    python -m app.evaluation.run --solo-informe   # solo compara (no llama a la IA)
    python -m app.evaluation.run --limite 10      # procesa como mucho 10 imágenes nuevas

- Usa una base aparte (<tu base>_evaluacion, con las mismas tablas de db/*.sql) y un almacenamiento
  aparte (backend/storage_eval): no se mezcla con tus datos. La caché de la IA sí se comparte:
  repetir no gasta cuota.
- Cada imagen se procesa por separado. Si se agota la cuota, se detiene; al volver a ejecutarlo
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
from sqlmodel import Session, col, select

from app.ai.client import AIError
from app.core.config import BACKEND_DIR, settings
from app.db import schema
from app.evaluation.compare import OBSERVATIONS, TYPE_CODES, compare, report
from app.models import DocumentoProcesado, TipoDocumento
from app.pipeline.preprocess import PreprocessError, detect_type
from app.pipeline.process import DocumentResult, QuotaExhausted, process_file
from app.storage import get_storage, original_key

SAMPLES = BACKEND_DIR.parent / "muestras"
IMAGES = SAMPLES / "imagenes"
ANSWERS = SAMPLES / "respuestas.json"
RESULTS = SAMPLES / "resultados"
TYPE_NAMES = {code: name for name, code in TYPE_CODES.items()}
STATES = {observation: state for state, observation in OBSERVATIONS.items()}


def _eval_engine():
    """Base <nombre>_evaluacion en el mismo servidor; se crea (con sus tablas) si no existe."""
    url = make_url(settings.DATABASE_URL)
    name = f"{url.database}_evaluacion"
    admin = url.set(drivername="postgresql", database="postgres").render_as_string(hide_password=False)
    with psycopg.connect(admin, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            conn.execute(f'CREATE DATABASE "{name}"')
    eval_url = url.set(database=name).render_as_string(hide_password=False)
    schema.ensure_schema(eval_url)
    return create_engine(eval_url)


def _images() -> list[Path]:
    files = [p for p in IMAGES.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".pdf")]
    return sorted(files, key=lambda p: [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", p.name)])


def _stored_row(session: Session, result: DocumentResult) -> DocumentoProcesado | None:
    """La fila del documento: la recién guardada o, si era duplicado, la que ya estaba."""
    if result.id is not None:
        return session.get(DocumentoProcesado, result.id)
    if result.resultado != "DUPLICADO":
        return None
    return session.exec(
        select(DocumentoProcesado)
        .join(TipoDocumento, col(TipoDocumento.id) == DocumentoProcesado.id_tipo_documento)
        .where(TipoDocumento.documento == result.tipo, DocumentoProcesado.folio == result.folio)
        .order_by(col(DocumentoProcesado.id))
    ).first()


def _summary(session: Session, results: list[DocumentResult]) -> dict:
    documents, errors = [], []
    for result in results:
        if result.resultado == "ERROR":
            errors.append(result.mensaje)
        row = _stored_row(session, result)
        if row is None:
            continue
        documents.append(
            {
                "tipo": result.tipo,
                "estado": row.observaciones,
                "rut": None if row.rut_proveedor == "1-9" else row.rut_proveedor,
                "numero": row.folio,
                "fecha": row.fecha.isoformat() if row.fecha else None,
                "neto": row.total_neto,
                "iva": row.iva,
                "impuestos": row.impuestos,
                "total": row.total,
                "firma": row.firma,
            }
        )
    return {"documentos": documents, "errores": errors}


def process(engine, system: dict[str, dict], limit: int | None) -> dict[str, dict]:
    """Procesa las imágenes que aún no tienen resultado. Devuelve los resultados (los previos + nuevos)."""
    storage = get_storage()
    new = 0
    for path in _images():
        if path.name in system:
            continue
        if limit is not None and new >= limit:
            break
        new += 1
        print(f"→ {path.name} …", flush=True)
        data = path.read_bytes()
        content_type, extension = detect_type(data)
        key = original_key(hashlib.sha256(data).hexdigest(), extension)
        storage.put(key, data)
        with Session(engine) as session:
            try:
                results = process_file(session, key, content_type)
            except QuotaExhausted:
                print("  ✖ Se agotó la cuota de la IA (o la clave fue rechazada). Vuelve a ejecutarlo más tarde.")
                break
            except (PreprocessError, AIError) as exc:
                print(f"  ✖ {path.name}: {exc}")
                continue
            system[path.name] = _summary(session, results)
        docs = system[path.name]["documentos"]
        print(f"  {path.name}: " + ("; ".join(f"{d['tipo']} {d['estado']}" for d in docs) or "sin documentos"), flush=True)
    return system


def _as_answer(doc: dict) -> dict:
    """Lo leído por el sistema en el formato de respuestas.json (para prellenar las nuevas)."""
    return {
        "tipo": TYPE_NAMES[doc["tipo"]],
        "estado": STATES[doc["estado"]],
        **{k: doc[k] for k in ("rut", "numero", "fecha", "neto", "iva")},
        "otros_impuestos": doc["impuestos"],
        "exento": None,
        "total": doc["total"],
        "firma": doc["firma"],
    }


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
        answers.append({"archivo": name, "revisado": False, "documentos": [_as_answer(d) for d in system[name]["documentos"]]})
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
    RESULTS.mkdir(parents=True, exist_ok=True)
    previous = RESULTS / "sistema.json"
    system = json.loads(previous.read_text(encoding="utf-8")) if previous.is_file() else {}

    if not args.solo_informe:
        system = process(_eval_engine(), system, args.limite)
        previous.write_text(json.dumps(system, ensure_ascii=False, indent=2), encoding="utf-8")

    answers = _load_answers()
    added = _save_answers(answers, system)
    reviewed = [a for a in answers if a.get("revisado")]
    totals = compare(reviewed, system)
    text = report(totals, pending=len(answers) - len(reviewed))
    (RESULTS / "informe.md").write_text(text, encoding="utf-8")

    print(f"\nProcesadas: {len(system)} de {len(_images())} imágenes. Respuestas nuevas por revisar: {added}.")
    print(f"Revisadas: {len(reviewed)}. Informe: {RESULTS / 'informe.md'}")


if __name__ == "__main__":
    main()
