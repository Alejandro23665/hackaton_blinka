"""Perfiles (tabla usuarios): alta desde la terminal y administrador inicial.

    python -m app.usuarios crear              # pregunta nombre, email, rol y contraseña
    python -m app.usuarios listar
    python -m app.usuarios admin-inicial      # crea el administrador de ADMIN_EMAIL si no existe

La contraseña se pide sin mostrarla y se guarda solo su hash. La API de perfiles (app/api/usuarios.py)
usa las mismas reglas.
"""
import getpass
import sys

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.auth import hash_password
from app.core.config import settings
from app.db.session import engine
from app.models import ADMIN_ROLE, MODEL_ROLE, Rol, Usuario

MIN_PASSWORD = 8


class InvalidUser(ValueError):
    pass


def roles(session: Session) -> dict[str, int]:
    """Los roles que puede tener una persona (todos menos el de la IA): nombre → id."""
    return {r.rol: r.id for r in session.exec(select(Rol).order_by(col(Rol.id))).all() if r.rol != MODEL_ROLE}


def add_user(session: Session, name: str, email: str, role: str, password: str) -> Usuario:
    """Crea un perfil activo. InvalidUser si los datos no sirven o el email ya existe."""
    name, email, role = name.strip(), email.strip(), role.strip().upper()
    available = roles(session)
    if not name:
        raise InvalidUser("Falta el nombre.")
    if "@" not in email:
        raise InvalidUser("El email no es válido.")
    if role not in available:
        raise InvalidUser(f"El rol debe ser {' o '.join(available)}.")
    if len(password) < MIN_PASSWORD:
        raise InvalidUser(f"La contraseña debe tener al menos {MIN_PASSWORD} caracteres.")
    user = Usuario(nombre=name, email=email, contrasena_hash=hash_password(password), id_rol=available[role])
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise InvalidUser(f"Ya existe un perfil con el email {email}.") from exc
    session.refresh(user)
    return user


def ensure_admin(session: Session) -> str:
    """Crea el administrador inicial (ADMIN_EMAIL y ADMIN_PASSWORD) si su email no existe. No cambia
    un perfil que ya existe: su contraseña y su rol se administran desde la aplicación."""
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return "Administrador inicial: define ADMIN_EMAIL y ADMIN_PASSWORD para crearlo."
    exists = session.exec(
        select(Usuario.id).where(func.lower(col(Usuario.email)) == settings.ADMIN_EMAIL.strip().lower())
    ).first()
    if exists is not None:
        return f"Administrador inicial: {settings.ADMIN_EMAIL} ya existe, no se cambió."
    add_user(session, settings.ADMIN_NOMBRE, settings.ADMIN_EMAIL, ADMIN_ROLE, settings.ADMIN_PASSWORD)
    return f"Administrador inicial creado: {settings.ADMIN_EMAIL}"


def create() -> None:
    with Session(engine) as session:
        available = roles(session)
        name = input("Nombre: ")
        email = input("Email: ")
        role = input(f"Rol ({', '.join(available)}): ")
        password = getpass.getpass(f"Contraseña (mínimo {MIN_PASSWORD} caracteres): ")
        if password != getpass.getpass("Repite la contraseña: "):
            sys.exit("Las contraseñas no coinciden.")
        try:
            user = add_user(session, name, email, role, password)
        except InvalidUser as exc:
            sys.exit(str(exc))
        print(f"Usuario creado: {user.nombre} <{user.email}> ({role.strip().upper()})")


def show() -> None:
    with Session(engine) as session:
        rows = session.exec(select(Usuario, Rol.rol).join(Rol, Rol.id == Usuario.id_rol).order_by(col(Usuario.id))).all()
        for user, role in rows:
            state = "" if user.activo else "  (desactivado)"
            print(f"{user.id:>4}  {role:<14} {user.nombre} <{user.email}>{state}")


def initial_admin() -> None:
    with Session(engine) as session:
        try:
            print(ensure_admin(session))
        except InvalidUser as exc:
            sys.exit(f"Administrador inicial: {exc}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"crear": create, "listar": show, "admin-inicial": initial_admin}.get(command, lambda: sys.exit(__doc__))()
