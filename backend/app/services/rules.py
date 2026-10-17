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
    return RuleResult("vendor_allowed", False, HARD, f"{vendor.name} no está autorizado")


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


def check_max_amount(invoice: Invoice, policy: Policy) -> RuleResult:
    limit = policy.max_amount_per_invoice
    if invoice.amount <= limit:
        return RuleResult(
            "max_amount_per_invoice",
            True,
            HARD,
            f"{_money(invoice.amount)} <= máximo por factura {_money(limit)}",
        )
    return RuleResult(
        "max_amount_per_invoice",
        False,
        HARD,
        f"{_money(invoice.amount)} supera el máximo por factura {_money(limit)}",
    )


def check_period_budget(invoice: Invoice, policy: Policy, spent: Decimal) -> RuleResult:
    total = spent + invoice.amount
    budget = policy.period_budget
    detail = (
        f"Gastado {_money(spent)} + {_money(invoice.amount)} = {_money(total)}"
        f" frente a presupuesto {_money(budget)}"
    )
    return RuleResult("period_budget", total <= budget, HARD, detail)


def check_require_human(invoice: Invoice, policy: Policy) -> RuleResult:
    threshold = policy.require_human_above
    if invoice.amount <= threshold:
        return RuleResult(
            "require_human_above",
            True,
            SOFT,
            f"{_money(invoice.amount)} <= umbral de revisión {_money(threshold)}",
        )
    return RuleResult(
        "require_human_above",
        False,
        SOFT,
        f"{_money(invoice.amount)} supera el umbral de revisión {_money(threshold)}",
    )


def evaluate(
    invoice: Invoice, vendor: Vendor, policy: Policy | None, spent_in_period: Decimal
) -> Evaluation:
    rules = [check_vendor_allowed(vendor), check_active_policy(policy)]
    if policy is not None:
        rules += [
            check_currency_allowed(invoice, policy),
            check_max_amount(invoice, policy),
            check_period_budget(invoice, policy, spent_in_period),
            check_require_human(invoice, policy),
        ]

    hard_failures = [r for r in rules if not r.passed and r.severity == HARD]
    soft_failures = [r for r in rules if not r.passed and r.severity == SOFT]

    if hard_failures:
        outcome = "blocked"
        explanation = "Bloqueada: " + "; ".join(r.detail for r in hard_failures) + "."
    elif soft_failures:
        outcome = "escalated"
        explanation = (
            "Escalada a revisión humana: " + "; ".join(r.detail for r in soft_failures) + "."
        )
    else:
        outcome = "approved"
        explanation = f"Aprobada: cumple todas las reglas de la política '{policy.name}'."

    return Evaluation(outcome=outcome, rules=rules, explanation=explanation)
