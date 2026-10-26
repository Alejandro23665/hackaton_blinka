"""Inicio de sesión con email y contraseña (tabla usuarios)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from app.api.deps import SessionDep
from app.auth import CurrentUser, authenticate, create_token
from app.models import Rol

router = APIRouter(prefix="/auth", tags=["sesión"])


class LoginIn(BaseModel):
    email: str
    contrasena: str


class UsuarioRead(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str


class LoginOut(BaseModel):
    token: str
    usuario: UsuarioRead


@router.post("/login", response_model=LoginOut)
def login(data: LoginIn, session: SessionDep):
    found = authenticate(session, data.email, data.contrasena)
    if found is None:
        raise HTTPException(401, "Email o contraseña incorrectos")
    user, role = found
    return LoginOut(
        token=create_token(user.id),
        usuario=UsuarioRead(id=user.id, nombre=user.nombre, email=user.email, rol=role),
    )


@router.get("/yo", response_model=UsuarioRead)
def me(user: CurrentUser, session: SessionDep):
    role = session.exec(select(Rol.rol).where(Rol.id == user.id_rol)).one()
    return UsuarioRead(id=user.id, nombre=user.nombre, email=user.email, rol=role)
