"""Prepara la base para la demo con la empresa ficticia Andes Digital LLC (dataset/manifest.json).

Uso (desde backend/):
    python -m app.demo                 # añade la política, tipos de cambio y proveedores de la demo
    python -m app.demo --reset         # BORRA todos los datos (y archivos subidos) y carga la demo
    python -m app.demo --reset --yes   # igual, sin pedir confirmación

No carga facturas: en la demo se suben en directo (dataset/invoices) para ver decidir al agente.
El reto prohíbe datos reales; --reset deja la base solo con datos ficticios.
"""
import argparse
import json
import sys
from decimal import Decimal

from sqlalchemy import func, text, update
from sqlmodel import Session, col, select

from app.db.session import engine
from app.evaluation import INVOICES_DIR, MANIFEST
from app.models import Decision, Document, ExchangeRate, Invoice, Policy, Vendor
from app.schemas import normalize_tax_id

TABLES = "documents, decisions, invoices, vendors, policies, exchange_rates"


def counts(session: Session) -> dict[str, int]:
    models = {"facturas": Invoice, "decisiones": Decision, "documentos": Document, "proveedores": Vendor, "políticas": Policy}
    return {name: session.exec(select(func.count()).select_from(model)).one() for name, model in models.items()}


def reset(session: Session) -> None:
    # CASCADE vacía también document_files (el contenido de los archivos)
    session.exec(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    session.commit()


def load(session: Session, manifest: dict) -> list[str]:
    done = []
    # Política: la de la demo queda como única activa (sin duplicarla si ya lo está)
    active = session.exec(select(Policy).where(col(Policy.is_active))).first()
    if active is None or active.name != manifest["policy"]["name"]:
        session.exec(update(Policy).where(col(Policy.is_active)).values(is_active=False))
        session.flush()
        session.add(Policy(**manifest["policy"], is_active=True))
    done.append(f"Política activa: {manifest['policy']['name']}")

    for currency, usd in manifest["exchange_rates"].items():
        rate = session.get(ExchangeRate, currency) or ExchangeRate(currency=currency, usd_per_unit=Decimal(0))
        rate.usd_per_unit = Decimal(str(usd))
        session.add(rate)
    done.append("Tipos de cambio: " + ", ".join(manifest["exchange_rates"]))

    added = []
    for v in manifest["vendors"]:
        tax_id = normalize_tax_id(v.get("tax_id"))
        exists = session.exec(
            select(Vendor).where((Vendor.tax_id == tax_id) | (func.lower(Vendor.name) == v["name"].lower()))
        ).first()
        if not exists:
            session.add(Vendor(**{**v, "tax_id": tax_id}))
            added.append(v["name"])
    done.append(f"Proveedores añadidos: {len(added)} de {len(manifest['vendors'])}")
    session.commit()
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga la empresa ficticia de la demo.")
    parser.add_argument("--reset", action="store_true", help="borra TODOS los datos y archivos antes de cargar")
    parser.add_argument("--yes", "-y", action="store_true", help="no pedir confirmación")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    with Session(engine) as session:
        before = counts(session)
        print(f"Base: {engine.url.database}")
        print("Ahora contiene: " + ", ".join(f"{n} {k}" for k, n in before.items()))
        if args.reset and not args.yes:
            print("\n--reset borrará TODO lo anterior, incluidos los archivos subidos. No se puede deshacer.")
            if input("Escribe 'borrar' para continuar: ").strip().lower() != "borrar":
                print("Cancelado.")
                return 1
        if args.reset:
            reset(session)
            print("Base vaciada.")
        for line in load(session, manifest):
            print("· " + line)

    print(f"\nListo. Para la demo, sube en este orden los archivos de {INVOICES_DIR}:")
    for case in manifest["invoices"]:
        print(f"  {case['file']:<36} → {case['case']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
