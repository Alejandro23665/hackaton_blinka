"""Motor de reglas: funciones puras, sin acceso a base de datos.

Cada regla devuelve un RuleResult. La severidad decide el resultado final:
- "hard": si falla, la factura se bloquea.
- "soft": si falla, la factura se escala a un humano.

Precedencia: cualquier hard falla -> blocked; si no, cualquier soft falla -> escalated;
si no -> approved. Siempre se evalúan todas las reglas para mostrarlas completas.
"""
from dataclasses import asdict, dataclass
from decimal import Decimal

from app.models import Invoice, Policy, Vendor
from app.services import fx
from app.services.fx import Conversion

HARD = "hard"
SOFT = "soft"


@dataclass(frozen=True)
class RuleResult:
    rule: str
    passed: bool
    severity: str
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Evaluation:
    outcome: str
    rules: list[RuleResult]
    explanation: str


def _money(value: Decimal) -> str:
    """Formato español: 9.000,00"""
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def check_vendor_allowed(vendor: Vendor) -> RuleResult:
    if vendor.is_allowed:
        return RuleResult("vendor_allowed", True, HARD, f"{vendor.name} está autorizado")
    if vendor.needs_review:
        # Proveedor nuevo detectado en una factura subida: decide una persona
        return RuleResult(
            "vendor_allowed", False, SOFT, f"{vendor.name} es un proveedor nuevo pendiente de aprobación"
        )
    return RuleResult("vendor_allowed", False, HARD, f"{vendor.name} no está autorizado")


def check_extraction(extraction: dict, min_confidence: float) -> RuleResult:
    confidence = float(extraction.get("confidence") or 0)
    warnings = extraction.get("warnings") or []
    pct = f"{confidence:.0%}"
    if confidence < min_confidence:
        detail = f"Confianza de lectura {pct} (mínimo {min_confidence:.0%})"
    elif warnings:
        detail = "Lectura con avisos: " + "; ".join(w.strip().rstrip(".") for w in warnings) + "."
    else:
        return RuleResult("document_extraction", True, SOFT, f"Datos leídos del documento con confianza {pct}")
    return RuleResult("document_extraction", False, SOFT, detail)


STATUS_LABELS = {
    "pending": "pendiente",
    "approved": "aprobada",
    "escalated": "escalada",
    "blocked": "bloqueada",
    "paid": "pagada",
}


def check_duplicate(invoice: Invoice, vendor: Vendor, original: Invoice | None) -> RuleResult:
    """Una factura con el mismo número y proveedor que otra ya registrada nunca se paga dos veces."""
    if original is None:
        return RuleResult(
            "duplicate_invoice", True, HARD, f"No hay otra factura {invoice.invoice_number} de {vendor.name}"
        )
    received = original.created_at.strftime("%d/%m/%Y") if original.created_at else "antes"
    return RuleResult(
        "duplicate_invoice",
        False,
        HARD,
        f"Ya existe la factura {original.invoice_number} de {vendor.name} (id {original.id}, "
        f"{_money(original.amount)} {original.currency}, {STATUS_LABELS.get(original.status, original.status)}, "
        f"recibida el {received}); pagarla otra vez sería un pago duplicado",
    )


def _pct(value: Decimal) -> str:
    """+58,3 % / -4,0 %"""
    return f"{value:+.1f} %".replace(".", ",")


def check_agreement(invoice: Invoice, vendor: Vendor, rates: fx.Rates) -> RuleResult:
    """La factura debe coincidir con lo acordado con el proveedor (monto ± tolerancia y moneda).

    Severidad soft: una diferencia puede ser legítima (ajuste, trabajo extra), así que no se bloquea,
    pero tampoco se aprueba sola: la revisa una persona.
    """
    if vendor.agreed_amount is None or not vendor.agreed_currency:
        return RuleResult("agreement_match", True, SOFT, f"Sin acuerdo registrado con {vendor.name}: no se compara")

    agreed_currency = vendor.agreed_currency.upper()
    agreed = Decimal(vendor.agreed_amount)
    tolerance = Decimal(vendor.agreement_tolerance_pct)
    notes = (vendor.agreement_notes or "").strip().rstrip(".")
    about = f". Acuerdo: {notes}" if notes else ""
    agreed_text = f"{_money(agreed)} {agreed_currency}"
    tolerance_text = f"±{tolerance.normalize():f} %"

    conv = fx.convert(invoice.amount, invoice.currency, agreed_currency, rates)
    if not conv.ok:
        return RuleResult(
            "agreement_match",
            False,
            SOFT,
            f"No se puede comparar con lo acordado ({agreed_text}): falta el tipo de cambio de "
            f"{invoice.currency} a {agreed_currency}{about}",
        )

    invoiced = f"{_money(conv.amount)} {conv.currency}"
    if not conv.same_currency:
        invoiced += f" (= {_money(conv.converted)} {agreed_currency})"
    deviation = (conv.converted - agreed) / agreed * 100

    if not conv.same_currency:
        return RuleResult(
            "agreement_match",
            False,
            SOFT,
            f"Lo acordado con {vendor.name} es en {agreed_currency} ({agreed_text}) pero la factura viene en "
            f"{invoice.currency}: {invoiced}{about}",
        )
    if abs(deviation) > tolerance:
        return RuleResult(
            "agreement_match",
            False,
            SOFT,
            f"No cuadra con lo acordado con {vendor.name}: factura {invoiced} frente a {agreed_text} "
            f"acordados ({_pct(deviation)}, tolerancia {tolerance_text}){about}",
        )
    return RuleResult(
        "agreement_match",
        True,
        SOFT,
        f"Coincide con lo acordado con {vendor.name}: {agreed_text} {tolerance_text}; factura {invoiced} "
        f"({_pct(deviation)}){about}",
    )


def check_invoice_totals(extraction: dict) -> RuleResult:
    """En facturas leídas de un archivo: subtotal + impuestos debe dar el total."""
    data = extraction.get("data") or {}
    subtotal, tax, total = data.get("subtotal"), data.get("tax_amount"), data.get("total_amount")
    if subtotal is None or total is None:
        return RuleResult(
            "invoice_totals", True, SOFT, "La factura no desglosa subtotal e impuestos: no se puede comprobar la suma"
        )
    subtotal, total = Decimal(str(subtotal)), Decimal(str(total))
    tax = Decimal(str(tax)) if tax is not None else Decimal(0)
    expected = subtotal + tax
    # Margen mínimo por redondeos de la lectura: 5 céntimos o 0,1 % del total
    margin = max(Decimal("0.05"), abs(total) * Decimal("0.001"))
    detail = f"Subtotal {_money(subtotal)} + impuestos {_money(tax)} = {_money(expected)}"
    if abs(expected - total) <= margin:
        return RuleResult("invoice_totals", True, SOFT, f"{detail}, igual al total de la factura")
    return RuleResult(
        "invoice_totals",
        False,
        SOFT,
        f"Los importes no cuadran: {detail}, pero la factura dice {_money(total)} "
        f"(diferencia {_money(abs(total - expected))})",
    )


def check_active_policy(policy: Policy | None) -> RuleResult:
    if policy is not None:
        return RuleResult("active_policy", True, SOFT, f"Política activa: {policy.name}")
    return RuleResult(
        "active_policy", False, SOFT, "No hay política activa; se requiere revisión humana"
    )


def check_currency_allowed(invoice: Invoice, policy: Policy) -> RuleResult:
    allowed = [c.upper() for c in policy.allowed_currencies]
    if invoice.currency.upper() in allowed:
        return RuleResult("currency_allowed", True, HARD, f"{invoice.currency} permitida")
    return RuleResult(
        "currency_allowed",
        False,
        HARD,
        f"{invoice.currency} no está entre las monedas permitidas ({', '.join(allowed)})",
    )


def _amount(conv: Conversion) -> str:
    """'4.900,00 GBP (= 6.223,00 USD)' o '4.900,00 USD' si ya está en la moneda base."""
    original = f"{_money(conv.amount)} {conv.currency}"
    if conv.same_currency or not conv.ok:
        return original
    return f"{original} (= {_money(conv.converted)} {conv.base_currency})"


def _rate(value: Decimal) -> str:
    """Tipo de cambio legible: hasta 6 decimales, sin ceros sobrantes, en formato español."""
    text = f"{value:,.6f}".rstrip("0").rstrip(".")
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _not_checkable(rule: str, conv: Conversion) -> RuleResult:
    return RuleResult(
        rule,
        False,
        SOFT,
        f"No se puede comprobar: falta el tipo de cambio de {conv.currency} a {conv.base_currency}",
    )


def check_currency_conversion(conv: Conversion) -> RuleResult:
    """Los límites están en la moneda base: sin tipo de cambio no se puede saber si se cumplen."""
    if conv.same_currency:
        return RuleResult(
            "currency_conversion", True, SOFT, f"Factura en {conv.currency}, la moneda base de la política"
        )
    if not conv.ok:
        return RuleResult(
            "currency_conversion",
            False,
            SOFT,
            f"No hay tipo de cambio configurado de {conv.currency} a {conv.base_currency}; "
            "sin él no se pueden comprobar los límites",
        )
    return RuleResult(
        "currency_conversion",
        True,
        SOFT,
        f"1 {conv.currency} = {_rate(conv.rate)} {conv.base_currency} (tipo de cambio configurado): "
        f"{_money(conv.amount)} {conv.currency} = {_money(conv.converted)} {conv.base_currency}",
    )


def check_max_amount(conv: Conversion, policy: Policy) -> RuleResult:
    if not conv.ok:
        return _not_checkable("max_amount_per_invoice", conv)
    limit = f"{_money(policy.max_amount_per_invoice)} {conv.base_currency}"
    if conv.converted <= policy.max_amount_per_invoice:
        return RuleResult("max_amount_per_invoice", True, HARD, f"{_amount(conv)} <= máximo por factura {limit}")
    return RuleResult("max_amount_per_invoice", False, HARD, f"{_amount(conv)} supera el máximo por factura {limit}")


def check_period_budget(
    conv: Conversion, policy: Policy, spent: Decimal, spent_missing: list[str] | None = None
) -> RuleResult:
    if not conv.ok:
        return _not_checkable("period_budget", conv)
    base = conv.base_currency
    if spent_missing:
        # Hay facturas aprobadas en monedas sin tipo de cambio: no se sabe cuánto queda
        return RuleResult(
            "period_budget",
            False,
            SOFT,
            f"No se puede calcular lo gastado en el periodo: faltan tipos de cambio de "
            f"{', '.join(spent_missing)} a {base}",
        )
    total = spent + conv.converted
    detail = (
        f"Gastado {_money(spent)} + {_money(conv.converted)} = {_money(total)} {base}"
        f" frente a presupuesto {_money(policy.period_budget)} {base}"
    )
    return RuleResult("period_budget", total <= policy.period_budget, HARD, detail)


def check_require_human(conv: Conversion, policy: Policy) -> RuleResult:
    if not conv.ok:
        return _not_checkable("require_human_above", conv)
    threshold = f"{_money(policy.require_human_above)} {conv.base_currency}"
    if conv.converted <= policy.require_human_above:
        return RuleResult("require_human_above", True, SOFT, f"{_amount(conv)} <= umbral de revisión {threshold}")
    return RuleResult("require_human_above", False, SOFT, f"{_amount(conv)} supera el umbral de revisión {threshold}")


def evaluate(
    invoice: Invoice,
    vendor: Vendor,
    policy: Policy | None,
    spent_in_period: Decimal,
    extraction: dict | None = None,
    min_confidence: float = 0.8,
    duplicate_of: Invoice | None = None,
    rates: fx.Rates | None = None,
    spent_missing: list[str] | None = None,
) -> Evaluation:
    """spent_in_period ya viene en la moneda base de la política; rates son los tipos de cambio."""
    rates = rates or {fx.PIVOT: Decimal(1)}
    rules = [
        check_vendor_allowed(vendor),
        check_duplicate(invoice, vendor, duplicate_of),
        check_agreement(invoice, vendor, rates),
        check_active_policy(policy),
    ]
    if extraction is not None:
        rules += [check_extraction(extraction, min_confidence), check_invoice_totals(extraction)]
    if policy is not None:
        conv = fx.convert(invoice.amount, invoice.currency, policy.base_currency, rates)
        rules += [
            check_currency_allowed(invoice, policy),
            check_currency_conversion(conv),
            check_max_amount(conv, policy),
            check_period_budget(conv, policy, spent_in_period, spent_missing),
            check_require_human(conv, policy),
        ]

    hard_failures = [r for r in rules if not r.passed and r.severity == HARD]
    soft_failures = [r for r in rules if not r.passed and r.severity == SOFT]

    def reasons(failures: list[RuleResult]) -> str:
        # Sin repetir: varias reglas pueden fallar por la misma causa (p. ej. falta un tipo de cambio)
        details = list(dict.fromkeys(r.detail.rstrip(".") for r in failures))
        return "; ".join(details) + "."

    if hard_failures:
        outcome = "blocked"
        explanation = "Bloqueada: " + reasons(hard_failures)
    elif soft_failures:
        outcome = "escalated"
        explanation = "Escalada a revisión humana: " + reasons(soft_failures)
    else:
        outcome = "approved"
        explanation = f"Aprobada: cumple todas las reglas de la política '{policy.name}'."

    return Evaluation(outcome=outcome, rules=rules, explanation=explanation)
