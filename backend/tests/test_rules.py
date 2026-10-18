"""Tests del motor de reglas: no necesitan base de datos."""
from datetime import date
from decimal import Decimal

from app.models import Invoice, Policy, Vendor
from app.services.rules import evaluate


def make_policy(**overrides) -> Policy:
    data = dict(
        name="Base",
        max_amount_per_invoice=Decimal("5000"),
        period_budget=Decimal("20000"),
        period="monthly",
        require_human_above=Decimal("1000"),
        allowed_currencies=["USD"],
    )
    return Policy(**{**data, **overrides})


def make_invoice(amount: str = "500", currency: str = "USD") -> Invoice:
    return Invoice(
        invoice_number="INV-1",
        vendor_id=1,
        amount=Decimal(amount),
        currency=currency,
        due_date=date(2026, 11, 1),
    )


ACME = Vendor(id=1, name="ACME", is_allowed=True)
SHADY = Vendor(id=2, name="Shady", is_allowed=False)


def failed(result) -> set[str]:
    return {r.rule for r in result.rules if not r.passed}


def test_approves_when_all_rules_pass():
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"))
    assert result.outcome == "approved"
    assert failed(result) == set()
    assert len(result.rules) == 9


def test_escalates_above_human_threshold():
    result = evaluate(make_invoice("1500"), ACME, make_policy(), Decimal("0"))
    assert result.outcome == "escalated"
    assert failed(result) == {"require_human_above"}


def test_amount_equal_to_threshold_is_approved():
    result = evaluate(make_invoice("1000"), ACME, make_policy(), Decimal("0"))
    assert result.outcome == "approved"


def test_blocks_vendor_not_allowed():
    result = evaluate(make_invoice("500"), SHADY, make_policy(), Decimal("0"))
    assert result.outcome == "blocked"
    assert failed(result) == {"vendor_allowed"}


def test_blocks_currency_not_allowed():
    result = evaluate(make_invoice("500", "EUR"), ACME, make_policy(), Decimal("0"), rates=RATES)
    assert result.outcome == "blocked"
    assert failed(result) == {"currency_allowed"}


def test_blocks_above_max_amount_even_if_also_needs_human():
    result = evaluate(make_invoice("6000"), ACME, make_policy(), Decimal("0"))
    assert result.outcome == "blocked"
    assert failed(result) == {"max_amount_per_invoice", "require_human_above"}
    assert "máximo por factura" in result.explanation


def test_blocks_when_budget_exceeded():
    result = evaluate(make_invoice("800"), ACME, make_policy(), Decimal("19500"))
    assert result.outcome == "blocked"
    assert failed(result) == {"period_budget"}


def test_budget_exactly_reached_is_allowed():
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("19500"))
    assert result.outcome == "approved"


def test_escalates_without_active_policy():
    result = evaluate(make_invoice("10"), ACME, None, Decimal("0"))
    assert result.outcome == "escalated"
    assert failed(result) == {"active_policy"}


def test_blocked_vendor_wins_over_missing_policy():
    result = evaluate(make_invoice("10"), SHADY, None, Decimal("0"))
    assert result.outcome == "blocked"


# --- Facturas leídas de un documento -------------------------------------------

PENDING = Vendor(id=3, name="Nuevo SAC", is_allowed=False, needs_review=True)
GOOD_EXTRACTION = {"confidence": 0.95, "warnings": []}


def test_new_pending_vendor_escalates_instead_of_blocking():
    result = evaluate(make_invoice("500"), PENDING, make_policy(), Decimal("0"))
    assert result.outcome == "escalated"
    assert failed(result) == {"vendor_allowed"}
    assert "pendiente de aprobación" in result.explanation


def test_document_with_good_extraction_is_approved():
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), extraction=GOOD_EXTRACTION)
    assert result.outcome == "approved"
    assert len(result.rules) == 11


def test_low_confidence_extraction_escalates():
    result = evaluate(
        make_invoice("500"), ACME, make_policy(), Decimal("0"), extraction={"confidence": 0.6, "warnings": []}
    )
    assert result.outcome == "escalated"
    assert failed(result) == {"document_extraction"}


def test_extraction_warnings_escalate():
    extraction = {"confidence": 0.9, "warnings": ["Moneda deducida por el símbolo $"]}
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), extraction=extraction)
    assert result.outcome == "escalated"
    assert "Moneda deducida" in result.explanation


def test_hard_rule_still_blocks_document_invoice():
    result = evaluate(make_invoice("9000"), ACME, make_policy(), Decimal("0"), extraction=GOOD_EXTRACTION)
    assert result.outcome == "blocked"


# --- Duplicados ------------------------------------------------------------------

def test_duplicate_invoice_is_blocked_with_reason():
    original = Invoice(
        id=9, invoice_number="INV-1", vendor_id=1, amount=Decimal("500"), currency="USD",
        due_date=date(2026, 11, 1), status="approved",
    )
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), duplicate_of=original)
    assert result.outcome == "blocked"
    assert failed(result) == {"duplicate_invoice"}
    assert "id 9" in result.explanation and "pago duplicado" in result.explanation


def test_duplicate_blocks_even_when_other_rules_would_escalate():
    original = Invoice(id=2, invoice_number="INV-1", vendor_id=1, amount=Decimal("1500"), currency="USD",
                       due_date=date(2026, 11, 1), status="escalated")
    result = evaluate(make_invoice("1500"), ACME, make_policy(), Decimal("0"), duplicate_of=original)
    assert result.outcome == "blocked"
    assert failed(result) == {"duplicate_invoice", "require_human_above"}


# --- Monedas -----------------------------------------------------------------------

RATES = {"USD": Decimal(1), "GBP": Decimal("1.27"), "EUR": Decimal("1.08"), "COP": Decimal("0.00025")}


def test_foreign_currency_over_limit_is_blocked_after_conversion():
    """El caso que motivó el cambio: 4.900 GBP parecen menos de 5.000, pero son 6.223 USD."""
    policy = make_policy(allowed_currencies=["USD", "GBP"])
    result = evaluate(make_invoice("4900", "GBP"), ACME, policy, Decimal("0"), rates=RATES)
    assert result.outcome == "blocked"
    assert "max_amount_per_invoice" in failed(result)
    assert "4.900,00 GBP (= 6.223,00 USD) supera el máximo por factura 5.000,00 USD" in result.explanation
    conversion = next(r for r in result.rules if r.rule == "currency_conversion")
    assert conversion.passed and "1 GBP = 1,27 USD" in conversion.detail


def test_small_foreign_amount_is_approved_and_shows_conversion():
    policy = make_policy(allowed_currencies=["USD", "COP"])
    result = evaluate(make_invoice("2000000", "COP"), ACME, policy, Decimal("0"), rates=RATES)
    assert result.outcome == "approved"  # 2.000.000 COP = 500 USD
    human = next(r for r in result.rules if r.rule == "require_human_above")
    assert "2.000.000,00 COP (= 500,00 USD)" in human.detail


def test_missing_exchange_rate_escalates_never_approves():
    policy = make_policy(allowed_currencies=["USD", "MXN"])
    result = evaluate(make_invoice("10", "MXN"), ACME, policy, Decimal("0"), rates=RATES)
    assert result.outcome == "escalated"
    assert failed(result) == {"currency_conversion", "max_amount_per_invoice", "period_budget", "require_human_above"}
    assert all(r.severity == "soft" for r in result.rules if not r.passed)
    assert "falta el tipo de cambio de MXN a USD" in result.explanation


def test_budget_not_checkable_when_spent_has_unconvertible_currency():
    result = evaluate(make_invoice("100"), ACME, make_policy(), Decimal("50"), rates=RATES, spent_missing=["MXN"])
    assert result.outcome == "escalated"
    assert failed(result) == {"period_budget"}


def test_policy_with_non_usd_base_currency():
    policy = make_policy(base_currency="EUR", allowed_currencies=["USD", "EUR"])
    # 1.080 USD = 1.000 EUR: justo en el umbral humano (1.000 EUR) -> no escala
    result = evaluate(make_invoice("1080", "USD"), ACME, policy, Decimal("0"), rates=RATES)
    assert result.outcome == "approved"
    assert any("1.080,00 USD (= 1.000,00 EUR)" in r.detail for r in result.rules)


def test_fx_convert_rounds_half_up_and_reports_missing():
    from app.services import fx

    assert fx.convert(Decimal("0.005"), "USD", "USD", RATES).converted == Decimal("0.01")
    assert fx.convert(Decimal("100"), "EUR", "GBP", RATES).converted == Decimal("85.04")
    assert fx.convert(Decimal("100"), "MXN", "USD", RATES).converted is None
    assert fx.missing_rates(["usd", "MXN", "eur"], "USD", RATES) == ["MXN"]


# --- Lo acordado con el proveedor y la suma de la factura -----------------------------

CONTRACTOR = Vendor(
    id=4, name="Ana Pérez", is_allowed=True, agreed_amount=Decimal("1200"), agreed_currency="USD",
    agreement_tolerance_pct=Decimal("5"), agreement_notes="Desarrollo, tarifa mensual",
)


def test_invoice_within_agreement_tolerance_is_approved():
    policy = make_policy(require_human_above=Decimal("3000"))  # aislar la regla del acuerdo
    result = evaluate(make_invoice("1230"), CONTRACTOR, policy, Decimal("0"), rates=RATES)
    assert result.outcome == "approved"
    rule = next(r for r in result.rules if r.rule == "agreement_match")
    assert rule.passed and "+2,5 %" in rule.detail and "Desarrollo, tarifa mensual" in rule.detail


def test_invoice_that_does_not_match_agreement_is_escalated():
    result = evaluate(make_invoice("1900"), CONTRACTOR, make_policy(require_human_above=Decimal("3000")), Decimal("0"), rates=RATES)
    assert result.outcome == "escalated"
    assert failed(result) == {"agreement_match"}
    assert "No cuadra con lo acordado con Ana Pérez" in result.explanation and "+58,3 %" in result.explanation


def test_invoice_below_agreement_is_also_escalated():
    result = evaluate(make_invoice("600"), CONTRACTOR, make_policy(), Decimal("0"), rates=RATES)
    assert result.outcome == "escalated"
    assert "-50,0 %" in result.explanation


def test_invoice_in_other_currency_than_agreed_is_escalated():
    policy = make_policy(allowed_currencies=["USD", "EUR"])
    result = evaluate(make_invoice("1100", "EUR"), CONTRACTOR, policy, Decimal("0"), rates=RATES)
    assert result.outcome == "escalated"
    assert "es en USD" in result.explanation and "viene en EUR" in result.explanation


def test_vendor_without_agreement_is_not_compared():
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), rates=RATES)
    rule = next(r for r in result.rules if r.rule == "agreement_match")
    assert rule.passed and "Sin acuerdo registrado" in rule.detail


def test_hard_rule_wins_over_agreement_mismatch():
    result = evaluate(make_invoice("9000"), CONTRACTOR, make_policy(), Decimal("0"), rates=RATES)
    assert result.outcome == "blocked"
    assert {"agreement_match", "max_amount_per_invoice"} <= failed(result)


def test_invoice_totals_that_do_not_add_up_are_escalated():
    extraction = {"confidence": 0.95, "warnings": [], "data": {"subtotal": 400, "tax_amount": 72, "total_amount": 500}}
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), extraction=extraction, rates=RATES)
    assert result.outcome == "escalated"
    assert failed(result) == {"invoice_totals"}
    assert "400,00 + impuestos 72,00 = 472,00, pero la factura dice 500,00" in result.explanation


def test_invoice_totals_tolerate_rounding_and_missing_breakdown():
    ok = {"confidence": 0.95, "warnings": [], "data": {"subtotal": 400, "tax_amount": 72.03, "total_amount": 472}}
    result = evaluate(make_invoice("472"), ACME, make_policy(), Decimal("0"), extraction=ok, rates=RATES)
    assert "invoice_totals" not in failed(result)
    no_breakdown = {"confidence": 0.95, "warnings": [], "data": {"total_amount": 472}}
    result = evaluate(make_invoice("472"), ACME, make_policy(), Decimal("0"), extraction=no_breakdown, rates=RATES)
    rule = next(r for r in result.rules if r.rule == "invoice_totals")
    assert rule.passed and "no desglosa" in rule.detail


def test_explanation_does_not_repeat_the_same_reason():
    policy = make_policy(allowed_currencies=["USD", "MXN"])
    result = evaluate(make_invoice("10", "MXN"), ACME, policy, Decimal("0"), rates=RATES)
    assert result.explanation.count("falta el tipo de cambio de MXN a USD") == 1


def test_informative_warnings_do_not_escalate():
    extraction = {"confidence": 0.95, "warnings": [{"text": "La factura no indica fecha de vencimiento", "critical": False}]}
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), extraction=extraction, rates=RATES)
    assert result.outcome == "approved"
    rule = next(r for r in result.rules if r.rule == "document_extraction")
    assert rule.passed and "avisos informativos" in rule.detail


def test_critical_warnings_escalate():
    extraction = {"confidence": 0.95, "warnings": [{"text": "El total está borroso", "critical": True}]}
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), extraction=extraction, rates=RATES)
    assert result.outcome == "escalated"
    assert "Lectura con dudas: El total está borroso" in result.explanation


def test_unclassified_warning_is_treated_as_critical():
    """Avisos antiguos (texto suelto) o sin clasificar: ante la duda, se escala."""
    extraction = {"confidence": 0.95, "warnings": ["Algo raro en el documento"]}
    result = evaluate(make_invoice("500"), ACME, make_policy(), Decimal("0"), extraction=extraction, rates=RATES)
    assert result.outcome == "escalated"
