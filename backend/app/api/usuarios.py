"""Perfiles del sistema (tabla usuarios), solo para administradores: listar, crear, cambiar el rol y
activar o desactivar. El "Modelo IA" no aparece ni se puede cambiar."""
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import col, select

from app.api.deps import SessionDep
from app.auth import AdminUser
from app.models import MODEL_ROLE, Rol, Usuario
from app.usuarios import MIN_PASSWORD, InvalidUser, add_user, roles

router = APIRouter(prefix="/usuarios", tags=["perfiles"])


class PerfilRead(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str
    activo: bool
    creado_en: datetime


class PerfilNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    email: str = Field(max_length=255)
    rol: str
    contrasena: str = Field(min_length=MIN_PASSWORD)


class PerfilCambio(BaseModel):
    """Lo que se cambia; lo que no viene queda igual."""

    rol: str | None = None
    activo: bool | None = None


def _read(session: SessionDep, user: Usuario) -> PerfilRead:
    return PerfilRead(rol=session.get(Rol, user.id_rol).rol, **user.model_dump(exclude={"contrasena_hash", "id_rol"}))


@router.get("", response_model=list[PerfilRead])
def list_profiles(session: SessionDep):
    """Todos los perfiles de personas, los activos primero y por nombre."""
    rows = session.exec(
        select(Usuario).join(Rol, col(Rol.id) == Usuario.id_rol).where(Rol.rol != MODEL_ROLE)
        .order_by(col(Usuario.activo).desc(), col(Usuario.nombre))
    ).all()
    return [_read(session, user) for user in rows]


@router.get("/roles", response_model=list[str])
def list_roles(session: SessionDep):
    return list(roles(session))


@router.post("", response_model=PerfilRead, status_code=201)
def create(data: PerfilNuevo, session: SessionDep):
    try:
        user = add_user(session, data.nombre, data.email, data.rol, data.contrasena)
    except InvalidUser as exc:
        raise HTTPException(422, str(exc)) from exc
    return _read(session, user)


@router.patch("/{usuario_id}", response_model=PerfilRead)
def update(usuario_id: int, data: PerfilCambio, session: SessionDep, admin: AdminUser):
    user = session.get(Usuario, usuario_id)
    if user is None or session.get(Rol, user.id_rol).rol == MODEL_ROLE:
        raise HTTPException(404, "Perfil no encontrado")
    # Así siempre queda al menos un administrador activo: quien hace el cambio
    if user.id == admin.id and (data.activo is False or (data.rol and data.rol.upper() != session.get(Rol, user.id_rol).rol)):
        raise HTTPException(400, "No puedes desactivar tu propio perfil ni quitarte el rol de administrador.")
    if data.rol is not None:
        available = roles(session)
        if data.rol.upper() not in available:
            raise HTTPException(422, f"El rol debe ser {' o '.join(available)}.")
        user.id_rol = available[data.rol.upper()]
    if data.activo is not None:
        user.activo = data.activo
    session.add(user)
    session.commit()
    session.refresh(user)
    return _read(session, user)
