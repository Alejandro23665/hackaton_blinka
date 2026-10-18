from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func
from sqlmodel import select

from app.api.deps import SessionDep
from app.models import Invoice, Vendor
from app.schemas import VendorCreate, VendorRead, VendorUpdate, check_agreement_complete

router = APIRouter(prefix="/vendors", tags=["vendors"])


def _ensure_unique_name(session: SessionDep, name: str, exclude_id: int | None = None) -> None:
    existing = session.exec(select(Vendor).where(Vendor.name == name)).first()
    if existing and existing.id != exclude_id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un proveedor llamado '{name}'")


def _ensure_unique_tax_id(session: SessionDep, tax_id: str | None, exclude_id: int | None = None) -> None:
    if not tax_id:
        return
    existing = session.exec(select(Vendor).where(Vendor.tax_id == tax_id)).first()
    if existing and existing.id != exclude_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"El ID fiscal {tax_id} ya pertenece al proveedor '{existing.name}'"
        )


@router.get("", response_model=list[VendorRead])
def list_vendors(session: SessionDep):
    return session.exec(select(Vendor).order_by(Vendor.name)).all()


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, session: SessionDep):
    _ensure_unique_name(session, payload.name)
    _ensure_unique_tax_id(session, payload.tax_id)
    data = payload.model_dump()
    if data["agreement_tolerance_pct"] is None:
        data.pop("agreement_tolerance_pct")  # usar el valor por defecto (5 %)
    vendor = Vendor(**data)
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    return vendor


@router.get("/{vendor_id}", response_model=VendorRead)
def get_vendor(vendor_id: int, session: SessionDep):
    vendor = session.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor no encontrado")
    return vendor


@router.patch("/{vendor_id}", response_model=VendorRead)
def update_vendor(vendor_id: int, payload: VendorUpdate, session: SessionDep):
    vendor = get_vendor(vendor_id, session)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        _ensure_unique_name(session, changes["name"], exclude_id=vendor_id)
    if "tax_id" in changes:
        _ensure_unique_tax_id(session, changes["tax_id"], exclude_id=vendor_id)
    if "is_allowed" in changes:
        changes["needs_review"] = False  # una persona ya decidió sobre este proveedor
    if changes.get("agreement_tolerance_pct", 0) is None:
        changes.pop("agreement_tolerance_pct")
    # Se valida el acuerdo resultante: se puede cambiar solo el monto o solo la moneda
    try:
        check_agreement_complete(
            changes.get("agreed_amount", vendor.agreed_amount),
            changes.get("agreed_currency", vendor.agreed_currency),
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    vendor.sqlmodel_update(changes)
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    return vendor


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(vendor_id: int, session: SessionDep):
    """Elimina un proveedor sin facturas. Si tiene facturas no se borra, para no perder el historial
    de pagos: en ese caso hay que bloquearlo."""
    vendor = get_vendor(vendor_id, session)
    invoices = session.exec(
        select(func.count()).select_from(Invoice).where(Invoice.vendor_id == vendor_id)
    ).one()
    if invoices:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{vendor.name} tiene {invoices} {'factura' if invoices == 1 else 'facturas'} y no se puede eliminar "
            "sin perder su historial. Elimina antes sus facturas desde su detalle (las aprobadas no se pueden "
            "borrar) o bloquéalo para que el agente rechace las nuevas.",
        )
    session.delete(vendor)
    session.commit()
