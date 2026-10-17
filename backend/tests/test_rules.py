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
    assert len(result.rules) == 6


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
    result = evaluate(make_invoice("500", "EUR"), ACME, make_policy(), Decimal("0"))
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
    assert len(result.rules) == 7


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
