"""Inicio de sesión con la tabla usuarios, sin dependencias externas.

- Contraseñas: scrypt (biblioteca estándar) con sal aleatoria. Se guarda solo el hash.
- Sesión: un token firmado con SECRET_KEY (HMAC-SHA256) que dice qué usuario es y hasta cuándo vale.
  Viaja en la cabecera `Authorization: Bearer <token>`.
- El usuario "Modelo IA" no puede iniciar sesión: su hash ('!') no es válido.
- Un perfil desactivado no puede iniciar sesión y sus sesiones abiertas dejan de valer.
"""
import base64
import hashlib
import hmac
import logging
import secrets
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.core.config import settings
from app.db.session import get_session
from app.models import ADMIN_ROLE, MODEL_ROLE, Rol, Usuario

SCRYPT = {"n": 2**14, "r": 8, "p": 1}

logger = logging.getLogger(__name__)
# Sin SECRET_KEY se usa una clave al azar: las sesiones se pierden al reiniciar el servidor
_secret = (settings.SECRET_KEY or secrets.token_urlsafe(32)).encode()
if not settings.SECRET_KEY:
    logger.warning("SECRET_KEY no está definida: las sesiones se cerrarán al reiniciar el servidor.")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = _unb64(digest)
        actual = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected))
    except ValueError:
        return False
    return hmac.compare_digest(actual, expected)


def _sign(payload: str) -> str:
    return _b64(hmac.new(_secret, payload.encode(), hashlib.sha256).digest())


def create_token(user_id: int) -> str:
    expires = int(time.time()) + settings.SESSION_HOURS * 3600
    payload = f"{user_id}.{expires}"
    return f"{payload}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    """El id del usuario, o None si el token es falso o venció."""
    try:
        user_id, expires, signature = token.split(".")
        if not hmac.compare_digest(signature, _sign(f"{user_id}.{expires}")) or int(expires) < time.time():
            return None
        return int(user_id)
    except ValueError:
        return None


def authenticate(session: Session, email: str, password: str) -> tuple[Usuario, str] | None:
    """El usuario y su rol si el email y la contraseña son correctos (nunca el Modelo IA)."""
    found = session.exec(
        select(Usuario, Rol.rol)
        .join(Rol, Rol.id == Usuario.id_rol)
        .where(func.lower(col(Usuario.email)) == email.strip().lower())
    ).first()
    if found is None or found[1] == MODEL_ROLE or not verify_password(password, found[0].contrasena_hash):
        return None
    return found


def current_user(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> Usuario:
    """Dependencia: el usuario de la sesión. 401 si no hay sesión válida."""
    if authorization and authorization.lower().startswith("bearer "):
        user_id = read_token(authorization[7:].strip())
        user = session.get(Usuario, user_id) if user_id is not None else None
        if user is not None and user.activo:
            return user
    raise HTTPException(401, "Inicia sesión para continuar", headers={"WWW-Authenticate": "Bearer"})


CurrentUser = Annotated[Usuario, Depends(current_user)]


def admin_user(user: CurrentUser, session: Annotated[Session, Depends(get_session)]) -> Usuario:
    """Dependencia: el usuario de la sesión, si es administrador. 403 si no lo es."""
    if session.get(Rol, user.id_rol).rol != ADMIN_ROLE:
        raise HTTPException(403, "Solo un administrador puede hacer esto")
    return user


AdminUser = Annotated[Usuario, Depends(admin_user)]
