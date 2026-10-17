"""Carga datos de ejemplo para la demo: python -m app.seed

Solo actúa si la base está vacía. Las facturas pasan por el agente, así que generan decisiones reales.
"""
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.db.session import engine
from app.models import Invoice, Policy, Vendor
from app.services import agent

VENDORS = [("ACME Suministros", True), ("Nube Cloud SA", True), ("Logística Rápida", True), ("Proveedor Dudoso", False)]

# (proveedor, número, monto, moneda) -> resultado esperado con la política de abajo
INVOICES = [
    ("ACME Suministros", "ACME-1001", "450.00", "USD"),  # aprobada
    ("Nube Cloud SA", "NC-2024-88", "1200.00", "USD"),  # aprobada
    ("Logística Rápida", "LR-551", "3800.00", "USD"),  # escalada (> 2.000)
    ("Proveedor Dudoso", "PD-01", "300.00", "USD"),  # bloqueada (proveedor)
    ("ACME Suministros", "ACME-1002", "9000.00", "USD"),  # bloqueada (> máximo)
    ("Nube Cloud SA", "NC-EU-3", "150.00", "EUR"),  # bloqueada (moneda)
]


def seed() -> None:
    with Session(engine) as session:
        if session.exec(select(Vendor)).first() or session.exec(select(Policy)).first():
            print("La base ya tiene datos; no se carga nada.")
            return

        session.add(
            Policy(
                name="Política base",
                max_amount_per_invoice=Decimal("5000"),
                period_budget=Decimal("20000"),
                period="monthly",
                require_human_above=Decimal("2000"),
                allowed_currencies=["USD"],
                is_active=True,
            )
        )
        vendors = {name: Vendor(name=name, is_allowed=allowed) for name, allowed in VENDORS}
        session.add_all(vendors.values())
        session.commit()

        for i, (vendor_name, number, amount, currency) in enumerate(INVOICES):
            vendor = vendors[vendor_name]
            invoice = Invoice(
                invoice_number=number,
                vendor_id=vendor.id,
                amount=Decimal(amount),
                currency=currency,
                due_date=date.today() + timedelta(days=15 + i * 5),
                raw_data={"source": "seed", "vendor": vendor_name, "number": number},
            )
            session.add(invoice)
            session.commit()
            decision = agent.evaluate_invoice(session, invoice)
            print(f"{number:<12} {amount:>9} {currency} -> {decision.outcome}")


if __name__ == "__main__":
    seed()
