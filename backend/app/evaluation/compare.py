"""Comparación de lo que leyó el sistema con las respuestas correctas (código puro, sin base de datos).

Respuesta correcta de un campo: su valor, o null si el documento no permite obtenerlo (ausente o
ilegible). Para cada campo se cuenta:
- correcto: el sistema dio el mismo valor (o tampoco dio valor cuando no lo hay);
- inventado: el sistema dio un valor distinto del correcto, o un valor donde no lo hay. Es el error
  grave: un dato falso que parece bueno;
- omitido: el sistema no dio valor donde sí lo hay (va a revisión humana: es un error seguro).
"""
from dataclasses import dataclass, field
from decimal import Decimal

FIELDS = ("rut", "numero", "fecha", "neto", "iva", "otros_impuestos", "exento", "total")
AMOUNTS = {"neto", "iva", "otros_impuestos", "exento", "total"}


def _same(name: str, expected, actual) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if name in AMOUNTS:
        return Decimal(str(expected)) == Decimal(str(actual))
    if name == "numero":
        return str(expected).lstrip("0") == str(actual).lstrip("0")
    return str(expected).strip().upper() == str(actual).strip().upper()


def _digits(value) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit()).lstrip("0")


def pair_documents(expected: list[dict], actual: list[dict]) -> list[tuple[dict | None, dict | None]]:
    """Empareja los documentos de una imagen: primero por tipo y número, luego por tipo y, al final,
    en orden. Así, con dos documentos en una foto, no importa en qué orden los encontró el sistema."""
    remaining = list(actual)
    pairs: list[tuple[dict | None, dict | None]] = []
    pending: list[dict] = []
    for exp in expected:
        match = next(
            (a for a in remaining if a["tipo"] == exp["tipo"] and _digits(a.get("numero")) and
             _digits(a.get("numero")) == _digits(exp.get("numero"))),
            None,
        )
        if match is None:
            pending.append(exp)
            continue
        remaining.remove(match)
        pairs.append((exp, match))
    still: list[dict] = []
    for exp in pending:
        match = next((a for a in remaining if a["tipo"] == exp["tipo"]), None)
        if match is None:
            still.append(exp)
            continue
        remaining.remove(match)
        pairs.append((exp, match))
    for index in range(max(len(still), len(remaining))):
        pairs.append((still[index] if index < len(still) else None, remaining[index] if index < len(remaining) else None))
    return pairs


@dataclass
class Totals:
    images: int = 0
    documents_expected: int = 0
    documents_found: int = 0
    images_with_count_mismatch: list[str] = field(default_factory=list)
    type_correct: int = 0
    type_total: int = 0
    state_correct: int = 0
    state_total: int = 0
    signature_correct: int = 0
    signature_total: int = 0
    fields: dict[str, dict[str, int]] = field(
        default_factory=lambda: {name: {"correcto": 0, "inventado": 0, "omitido": 0} for name in FIELDS}
    )
    invented: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


def compare(expected_images: list[dict], system: dict[str, dict]) -> Totals:
    """`expected_images`: respuestas revisadas. `system`: resultados del sistema por archivo."""
    totals = Totals()
    for image in expected_images:
        name = image["archivo"]
        found = system.get(name)
        totals.images += 1
        expected_docs = image.get("documentos", [])
        totals.documents_expected += len(expected_docs)
        if found is None:
            totals.errors.append({"archivo": name, "error": "el sistema aún no lo procesó"})
            continue
        actual_docs = found.get("documentos", [])
        totals.documents_found += len(actual_docs)
        if len(actual_docs) != len(expected_docs):
            totals.images_with_count_mismatch.append(name)
        # Los que sobran o faltan cuentan como error de clasificación
        for index, (exp, act) in enumerate(pair_documents(expected_docs, actual_docs)):
            totals.type_total += 1
            if exp is None or act is None:
                continue
            if exp["tipo"] == act["tipo"]:
                totals.type_correct += 1
            else:
                continue  # con otro tipo, los campos no son comparables
            totals.state_total += 1
            totals.state_correct += exp.get("estado") == act.get("estado")
            if exp["tipo"] == "DESCONOCIDO":
                continue
            if exp.get("firma") is not None:
                totals.signature_total += 1
                totals.signature_correct += exp["firma"] == act.get("firma")
            for field_name in FIELDS:
                expected_value, actual_value = exp.get(field_name), act.get(field_name)
                if _same(field_name, expected_value, actual_value):
                    totals.fields[field_name]["correcto"] += 1
                elif actual_value is None:
                    totals.fields[field_name]["omitido"] += 1
                else:
                    totals.fields[field_name]["inventado"] += 1
                    totals.invented.append(
                        {"archivo": name, "documento": index + 1, "campo": field_name,
                         "correcto": expected_value, "sistema": actual_value}
                    )
    return totals


def _pct(part: int, whole: int) -> str:
    return f"{part / whole * 100:.0f} % ({part}/{whole})" if whole else "—"


def report(totals: Totals, pending: int) -> str:
    lines = [
        "# Evaluación con muestras reales",
        "",
        f"Imágenes evaluadas: **{totals.images}** (respuestas revisadas). Pendientes de revisar: {pending}.",
        "",
        "| Métrica | Resultado |",
        "|---|---|",
        f"| Documentos esperados / encontrados | {totals.documents_expected} / {totals.documents_found} |",
        f"| Clasificación correcta | {_pct(totals.type_correct, totals.type_total)} |",
        f"| Estado final correcto | {_pct(totals.state_correct, totals.state_total)} |",
        f"| Firma correcta | {_pct(totals.signature_correct, totals.signature_total)} |",
        f"| **Datos inventados** | **{len(totals.invented)}** |",
        "",
        "## Por campo",
        "",
        "| Campo | Correcto | Omitido (a revisión) | **Inventado** |",
        "|---|---|---|---|",
    ]
    for name in FIELDS:
        counts = totals.fields[name]
        total = sum(counts.values())
        lines.append(
            f"| {name} | {_pct(counts['correcto'], total)} | {counts['omitido']} | **{counts['inventado']}** |"
        )
    if totals.invented:
        lines += ["", "## Datos inventados (revisar primero)", "", "| Archivo | Doc. | Campo | Correcto | Sistema |", "|---|---|---|---|---|"]
        lines += [
            f"| {i['archivo']} | {i['documento']} | {i['campo']} | {i['correcto']} | {i['sistema']} |"
            for i in totals.invented
        ]
    if totals.images_with_count_mismatch:
        lines += ["", "Imágenes con distinto número de documentos: " + ", ".join(totals.images_with_count_mismatch)]
    if totals.errors:
        lines += ["", "Sin resultado del sistema: " + ", ".join(e["archivo"] for e in totals.errors)]
    return "\n".join(lines) + "\n"
