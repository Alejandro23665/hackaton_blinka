from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import SessionDep
from app.models import Vendor
from app.schemas import VendorCreate, VendorRead, VendorUpdate

router = APIRouter(prefix="/vendors", tags=["vendors"])


def _ensure_unique_name(session: SessionDep, name: str, exclude_id: int | None = None) -> None:
    existing = session.exec(select(Vendor).where(Vendor.name == name)).first()
    if existing and existing.id != exclude_id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Ya existe un proveedor llamado '{name}'")


@router.get("", response_model=list[VendorRead])
def list_vendors(session: SessionDep):
    return session.exec(select(Vendor).order_by(Vendor.name)).all()


@router.post("", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
def create_vendor(payload: VendorCreate, session: SessionDep):
    _ensure_unique_name(session, payload.name)
    vendor = Vendor(**payload.model_dump())
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
    vendor.sqlmodel_update(changes)
    session.add(vendor)
    session.commit()
    session.refresh(vendor)
    return vendor
