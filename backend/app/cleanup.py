"""Limpia las facturas subidas: archivos locales y los registros creados a partir de ellos.

Uso (desde backend/):
    python -m app.cleanup            # muestra qué se borraría y pide confirmación
    python -m app.cleanup --dry-run  # solo muestra, no borra nada
    python -m app.cleanup --yes      # borra sin preguntar

Borra: documentos (con su archivo), las facturas creadas desde esos documentos,
sus decisiones y los proveedores que creó el agente (si ya no tienen otras facturas).
No toca: políticas, proveedores creados a mano ni facturas ingresadas manualmente.
"""
import argparse
import sys

from sqlalchemy import delete, func
from sqlmodel import Session, col, select

from app.db.session import engine
from app.models import Decision, Document, Invoice, Vendor
from app.services import storage


def plan(session: Session) -> dict:
    documents = session.exec(select(Document)).all()
    invoice_ids = [d.invoice_id for d in documents if d.invoice_id]
    invoices = session.exec(select(Invoice).where(col(Invoice.id).in_(invoice_ids))).all() if invoice_ids else []

    # Proveedores que creó el agente al leer estos documentos
    created_vendor_ids = {
        inv.vendor_id
        for inv in invoices
        if ((inv.raw_data or {}).get("extraction") or {}).get("vendor_created")
    }
    vendors = []
    for vendor_id in created_vendor_ids:
        others = session.exec(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.vendor_id == vendor_id, col(Invoice.id).not_in(invoice_ids))
        ).one()
        if not others:
            vendors.append(session.get(Vendor, vendor_id))

    return {"documents": documents, "invoices": invoices, "vendors": vendors}


def describe(p: dict) -> None:
    size_kb = sum(d.size_bytes for d in p["documents"]) / 1024
    print(f"Documentos: {len(p['documents'])} ({size_kb:,.0f} KB)")
    for d in p["documents"]:
        print(f"  - {d.original_name} [{d.status}]")
    print(f"Facturas creadas desde documentos: {len(p['invoices'])}")
    for inv in p["invoices"]:
        print(f"  - {inv.invoice_number} ({inv.amount} {inv.currency}, {inv.status})")
    print(f"Proveedores creados por el agente: {len(p['vendors'])}")
    for v in p["vendors"]:
        print(f"  - {v.name}")


def execute(session: Session, p: dict) -> None:
    invoice_ids = [inv.id for inv in p["invoices"]]
    if invoice_ids:
        session.exec(delete(Decision).where(col(Decision.invoice_id).in_(invoice_ids)))
    session.exec(delete(Document))  # su archivo (document_files) se borra en cascada
    if invoice_ids:
        session.exec(delete(Invoice).where(col(Invoice.id).in_(invoice_ids)))
    for vendor in p["vendors"]:
        session.delete(vendor)
    session.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Limpia las facturas subidas y sus registros.")
    parser.add_argument("--yes", "-y", action="store_true", help="no pedir confirmación")
    parser.add_argument("--dry-run", action="store_true", help="solo mostrar qué se borraría")
    args = parser.parse_args()

    with Session(engine) as session:
        p = plan(session)
        describe(p)
        if not p["documents"]:
            print("\nNo hay nada que limpiar.")
            return 0
        if args.dry_run:
            print("\nSimulación: no se borró nada.")
            return 0
        if not args.yes:
            answer = input("\n¿Borrar todo lo anterior? Escribe 'si' para confirmar: ").strip().lower()
            if answer not in ("si", "sí", "s"):
                print("Cancelado.")
                return 1
        execute(session, p)
        print("\nLimpieza completada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
