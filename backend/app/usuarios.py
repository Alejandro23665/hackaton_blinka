"""Alta de usuarios desde la terminal (la contraseña se pide sin mostrarla y se guarda solo su hash).

    python -m app.usuarios crear              # pregunta nombre, email, rol y contraseña
    python -m app.usuarios listar
"""
import getpass
import sys

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.auth import hash_password
from app.db.session import engine
from app.models import MODEL_ROLE, Rol, Usuario

MIN_PASSWORD = 8


def create() -> None:
    with Session(engine) as session:
        roles = {r.rol: r.id for r in session.exec(select(Rol).order_by(col(Rol.id))).all() if r.rol != MODEL_ROLE}
        name = input("Nombre: ").strip()
        email = input("Email: ").strip()
        role = input(f"Rol ({', '.join(roles)}): ").strip().upper()
        if not name or "@" not in email or role not in roles:
            sys.exit("Datos no válidos: hace falta nombre, un email y uno de los roles indicados.")
        password = getpass.getpass(f"Contraseña (mínimo {MIN_PASSWORD} caracteres): ")
        if len(password) < MIN_PASSWORD or password != getpass.getpass("Repite la contraseña: "):
            sys.exit("Las contraseñas no coinciden o son muy cortas.")
        session.add(Usuario(nombre=name, email=email, contrasena_hash=hash_password(password), id_rol=roles[role]))
        try:
            session.commit()
        except IntegrityError:
            sys.exit(f"Ya existe un usuario con el email {email}.")
        print(f"Usuario creado: {name} <{email}> ({role})")


def show() -> None:
    with Session(engine) as session:
        rows = session.exec(select(Usuario, Rol.rol).join(Rol, Rol.id == Usuario.id_rol).order_by(col(Usuario.id))).all()
        for user, role in rows:
            print(f"{user.id:>4}  {role:<14} {user.nombre} <{user.email}>")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    {"crear": create, "listar": show}.get(command, lambda: sys.exit(__doc__))()
