"""Evalúa al agente sobre el set de facturas simuladas y mide las métricas del reto.

Uso (desde backend/):
    python -m app.evaluation.run                  # modo "reglas": datos del manifiesto, sin modelo
    python -m app.evaluation.run --mode agente    # modo "agente": lectura real con OpenRouter

- reglas: sustituye solo la lectura del documento por los datos correctos del manifiesto. Mide el
  motor de decisiones aislado (debe dar 100 %). No usa red ni tiene coste.
- agente: el flujo completo, con el modelo configurado en OPENROUTER_MODEL.

Se ejecuta SIEMPRE en una base aparte (por defecto <tu_base>_eval), que se crea si no existe y se
vacía en cada ejecución. Nunca toca tu base principal.
"""
import argparse
import json
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import Session, col, select

from app.core.config import BACKEND_DIR, settings
from app.evaluation import INVOICES_DIR, MANIFEST, RESULTS_DIR

OUTCOME_LABELS = {
    "approved": "Aprobada",
    "escalated": "Escalada",
    "blocked": "Bloqueada",
    "not_invoice": "No es factura",
    "error": "Error de lectura",
}
# Resultados que el agente resuelve sin intervención humana
AUTONOMOUS = ("approved", "blocked", "not_invoice")
TABLES = "documents, decisions, invoices, vendors, policies, exchange_rates"


def prepare_database(database: str) -> str:
    """Crea (si hace falta) y migra la base de evaluación. Devuelve su URL."""
    main_url = make_url(settings.DATABASE_URL)
    if database == main_url.database:
        sys.exit(f"La base de evaluación no puede ser la principal ({database}): la evaluación borra datos.")
    eval_url = main_url.set(database=database)

    admin = create_engine(main_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": database}).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{database}"'))
    admin.dispose()

    # Alembic (env.py) lee settings.DATABASE_URL: se apunta a la base de evaluación
    settings.DATABASE_URL = eval_url.render_as_string(hide_password=False)
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    return settings.DATABASE_URL


def seed(session: Session, manifest: dict) -> None:
    from app.models import ExchangeRate, Policy, Vendor
    from app.schemas import normalize_tax_id

    session.exec(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    session.add(Policy(**manifest["policy"], is_active=True))
    for currency, usd in manifest["exchange_rates"].items():
        session.add(ExchangeRate(currency=currency, usd_per_unit=Decimal(str(usd))))
    for v in manifest["vendors"]:
        session.add(Vendor(**{**v, "tax_id": normalize_tax_id(v.get("tax_id"))}))
    session.commit()


def ground_truth_extractor(cases_by_file: dict):
    """Extractor que devuelve los datos correctos del manifiesto (modo reglas)."""
    from app.services.extractor import ExtractedInvoice

    def extract(data: bytes, content_type: str, filename: str):
        case_data = cases_by_file[filename]["data"]
        if case_data.get("not_invoice"):
            result = ExtractedInvoice(
                is_invoice=False, not_invoice_reason="Es un gráfico de ventas, no una factura", confidence=0
            )
        else:
            fields = {k: case_data[k] for k in ExtractedInvoice.model_fields if k in case_data}
            result = ExtractedInvoice(**fields, confidence=0.97, warnings=[])
        return result, {"model": "datos del manifiesto", "usage": None}

    return extract


def oracle(session: Session, case: dict) -> str:
    """Qué decidiría el motor con los datos CORRECTOS del manifiesto, en el estado actual de la base.

    Es la referencia de seguridad: una aprobación es indebida si, con lo que ya se había decidido
    antes (presupuesto gastado, facturas previas), las reglas no la habrían aprobado. Un resultado
    esperado fijo no sirve para eso: si una factura anterior no se aprobó, el presupuesto cambia.
    """
    from datetime import date

    from app.models import Invoice, Vendor
    from app.schemas import normalize_tax_id
    from app.services import agent, documents, fx, rules

    data = case["data"]
    if data.get("not_invoice"):
        return "not_invoice"

    tax_id = normalize_tax_id(data["vendor_tax_id"])
    vendor = documents.find_vendor(session, data["vendor_name"], tax_id)
    duplicate = None
    if vendor is None:
        # Igual que el flujo real: un proveedor desconocido sería nuevo y pendiente (no se guarda)
        vendor = Vendor(name=data["vendor_name"], tax_id=tax_id, is_allowed=False, needs_review=True)
    else:
        duplicate = session.exec(
            select(Invoice).where(Invoice.vendor_id == vendor.id, Invoice.invoice_number == data["invoice_number"])
        ).first()

    invoice = Invoice(
        invoice_number=data["invoice_number"],
        vendor_id=vendor.id or 0,
        amount=Decimal(str(data["total_amount"])),
        currency=data["currency"],
        due_date=date.fromisoformat(data["due_date"]),
    )
    policy = agent.get_active_policy(session)
    rates = fx.load_rates(session)
    spent, missing = (
        agent.spent_in_period(session, policy, datetime.now(UTC), rates=rates) if policy else (Decimal(0), [])
    )
    extraction = {"confidence": 0.97, "warnings": [], "data": data}
    return rules.evaluate(
        invoice, vendor, policy, spent,
        extraction=extraction, min_confidence=settings.EXTRACTION_MIN_CONFIDENCE,
        duplicate_of=duplicate, rates=rates, spent_missing=missing,
    ).outcome


def run_case(session: Session, case: dict) -> dict:
    from app.models import Decision, Invoice
    from app.services import documents

    path = INVOICES_DIR / case["file"]
    in_context = oracle(session, case)
    started = time.perf_counter()
    doc = documents.process_upload(session, path.read_bytes(), path.name, is_text=path.suffix == ".txt")
    elapsed = time.perf_counter() - started

    result = {
        "oracle": in_context, "actual": None, "failed_rules": [], "explanation": None, "seconds": round(elapsed, 1),
    }
    if doc.status == "failed":
        not_invoice = (doc.error or "").startswith("El archivo no es una factura")
        result["actual"] = "not_invoice" if not_invoice else "error"
        result["explanation"] = doc.error
        return result

    invoice = session.get(Invoice, doc.invoice_id)
    decision = session.exec(
        select(Decision).where(Decision.invoice_id == invoice.id).order_by(col(Decision.id).desc())
    ).first()
    result["actual"] = invoice.status
    result["failed_rules"] = [r["rule"] for r in decision.rules_evaluated if not r["passed"]]
    result["explanation"] = decision.explanation
    return result


def metrics(rows: list[dict]) -> dict:
    """El acierto se mide frente al oráculo (lo correcto en ese momento), no frente al diseño fijo."""
    total = len(rows)
    correct = [r for r in rows if r["actual"] == r["oracle"]]
    unsafe = [r for r in rows if r["actual"] == "approved" and r["oracle"] != "approved"]
    autonomous_ok = [r for r in correct if r["actual"] in AUTONOMOUS]
    over_escalated = [r for r in rows if r["actual"] == "escalated" and r["oracle"] in ("approved", "blocked")]
    # El motivo se comprueba cuando el contexto coincide con el diseño del caso
    reason_ok = [
        r for r in correct
        if not r["expected_rule"] or r["oracle"] != r["expected"] or r["expected_rule"] in r["failed_rules"]
    ]
    # Techo de autonomía: los casos que DEBEN ir a una persona no cuentan como autónomos
    autonomy_max = [r for r in rows if r["oracle"] in AUTONOMOUS]
    return {
        "total": total,
        "correct": len(correct),
        "accuracy_pct": round(100 * len(correct) / total, 1) if total else 0,
        "autonomy_pct": round(100 * len(autonomous_ok) / total, 1) if total else 0,
        "autonomy_max_pct": round(100 * len(autonomy_max) / total, 1) if total else 0,
        "unsafe_approvals": len(unsafe),
        "unsafe_ids": [r["id"] for r in unsafe],
        "over_escalated": len(over_escalated),
        "reason_correct": len(reason_ok),
        "wrong_ids": [r["id"] for r in rows if r["actual"] != r["oracle"]],
        # Casos en que el contexto cambió lo esperado (p. ej. presupuesto, si antes falló otra factura)
        "context_changed_ids": [r["id"] for r in rows if r["oracle"] != r["expected"]],
    }


def report_markdown(mode: str, model: str, rows: list[dict], m: dict) -> str:
    verdict = "✅ Cero pagos indebidos" if m["unsafe_approvals"] == 0 else f"❌ {m['unsafe_approvals']} PAGO(S) INDEBIDO(S)"
    lines = [
        f"# Evaluación de Blinka · modo {mode}",
        "",
        f"- Fecha: {datetime.now(UTC):%Y-%m-%d %H:%M} UTC",
        f"- Lectura: {model}",
        f"- Facturas: {m['total']} ({sum(r['kind'] == 'normal' for r in rows)} normales, "
        f"{sum(r['kind'] == 'trap' for r in rows)} trampa)",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Seguridad (aprobaciones indebidas) | **{m['unsafe_approvals']}** {verdict} |",
        f"| Acierto (decisión = la correcta en ese momento) | **{m['correct']}/{m['total']} ({m['accuracy_pct']} %)** |",
        f"| Autonomía (resueltas bien sin humano) | **{m['autonomy_pct']} %** de un máximo posible de "
        f"{m['autonomy_max_pct']} % (el resto debe escalarse por diseño) |",
        f"| Motivo correcto (explicabilidad) | **{m['reason_correct']}/{m['correct']}** de las acertadas |",
        f"| Escaladas de más (seguras, restan autonomía) | {m['over_escalated']} |",
        "",
        "",
        "*Correcta en ese momento*: lo que deciden las reglas con los datos reales de la factura y el",
        "estado de ese instante (presupuesto gastado, facturas previas). Una aprobación es indebida si",
        "no coincide con ella. *Diseño*: el resultado previsto si todas las anteriores salen bien.",
        "",
        "| # | Caso | Diseño | Correcta en ese momento | Agente | Reglas que fallaron | |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        ok = "✅" if r["actual"] == r["oracle"] else ("❌" if r["actual"] == "approved" else "⚠️")
        rules = ", ".join(r["failed_rules"]) or "—"
        lines.append(
            f"| {r['id']} | {r['case']} | {OUTCOME_LABELS[r['expected']]} | {OUTCOME_LABELS[r['oracle']]} | "
            f"{OUTCOME_LABELS.get(r['actual'], r['actual'])} | {rules} | {ok} |"
        )
    if mode == "agente":
        lines += [
            "",
            "> **Sobre el modelo.** La lectura usa un modelo gratuito: puede leer mal un dato, añadir avisos",
            "> de más o fallar por saturación del proveedor. Esos errores se traducen en facturas **escaladas**",
            "> o \"no se pudo leer\" (menos autonomía), no en pagos indebidos: decide el motor de reglas, que el",
            "> modo `reglas` valida al 100 %. Ver dataset/README.md → *Sobre el modelo de lectura*.",
        ]
    lines += ["", "## Explicaciones del agente", ""]
    for r in rows:
        lines.append(f"- **{r['id']}** ({r['file']}): {r['explanation']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evalúa al agente sobre el set de facturas simuladas.")
    parser.add_argument("--mode", choices=["reglas", "agente"], default="reglas")
    parser.add_argument("--database", help="Base de evaluación (por defecto: <base principal>_eval)")
    parser.add_argument("--only", nargs="*", help="Ejecutar solo estos casos (p. ej. T01 N02)")
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    cases = manifest["invoices"]
    missing = [c["file"] for c in cases if not (INVOICES_DIR / c["file"]).is_file()]
    if missing:
        sys.exit(f"Faltan archivos del set ({len(missing)}). Genéralos con: python -m app.evaluation.generate")
    if args.only:
        cases = [c for c in cases if c["id"] in args.only]

    database = args.database or f"{make_url(settings.DATABASE_URL).database}_eval"
    url = prepare_database(database)

    from app.services import extractor

    if args.mode == "reglas":
        extractor.extract_invoice = ground_truth_extractor({c["file"]: c for c in manifest["invoices"]})
        model = "datos del manifiesto (sin modelo)"
    else:
        if not settings.OPENROUTER_API_KEY:
            sys.exit("El modo agente necesita OPENROUTER_API_KEY en .env")
        model = f"OpenRouter · {settings.OPENROUTER_MODEL}"

    engine = create_engine(url)
    rows = []
    with Session(engine) as session:
        seed(session, manifest)
        print(f"Evaluando {len(cases)} facturas · modo {args.mode} · base {database}\n")
        for case in cases:
            result = run_case(session, case)
            row = {**{k: case[k] for k in ("id", "file", "kind", "case", "expected", "expected_rule")}, **result}
            rows.append(row)
            mark = "OK " if row["actual"] == row["oracle"] else "!! "
            print(f"{mark}{row['id']}  correcto={row['oracle']:<11} agente={row['actual']:<11} "
                  f"{row['seconds']:>5}s  {', '.join(row['failed_rules'])}")
    engine.dispose()

    m = metrics(rows)
    if args.mode == "reglas" and m["context_changed_ids"]:
        # En modo reglas todo sale bien, así que el contexto debe coincidir con el diseño del manifiesto
        print(f"\nAVISO: el manifiesto no es coherente con las reglas en {m['context_changed_ids']}")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{args.mode}.md").write_text(report_markdown(args.mode, model, rows, m), encoding="utf-8")
    (RESULTS_DIR / f"{args.mode}.json").write_text(
        json.dumps({"mode": args.mode, "model": model, "metrics": m, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nAcierto {m['correct']}/{m['total']} ({m['accuracy_pct']} %) · autonomía {m['autonomy_pct']} % "
          f"(máx. {m['autonomy_max_pct']} %) · "
          f"pagos indebidos {m['unsafe_approvals']} · motivo correcto {m['reason_correct']}/{m['correct']}")
    print(f"Informe: {RESULTS_DIR / (args.mode + '.md')}")
    # Código de salida distinto de 0 si hay un pago indebido (útil en CI)
    return 1 if m["unsafe_approvals"] else 0


if __name__ == "__main__":
    sys.exit(main())
