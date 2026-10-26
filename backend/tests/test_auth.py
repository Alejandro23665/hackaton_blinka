"""Inicio de sesión: contraseñas, tokens y rutas protegidas."""
from app.auth import create_token, hash_password, read_token, verify_password
from tests.conftest import PASSWORD, create_user


def test_password_hash_is_salted_and_verifiable():
    first, second = hash_password("secreto-largo"), hash_password("secreto-largo")
    assert first != second and "secreto-largo" not in first
    assert verify_password("secreto-largo", first) and not verify_password("otra", first)
    assert not verify_password("cualquiera", "!")  # el hash del Modelo IA no es válido


def test_token_cannot_be_forged():
    token = create_token(7)
    assert read_token(token) == 7
    user_id, expires, signature = token.split(".")
    assert read_token(f"8.{expires}.{signature}") is None
    assert read_token("basura") is None


def test_everything_but_login_and_health_requires_a_session(anonymous_client):
    assert anonymous_client.get("/health").status_code == 200
    for path in ("/documentos", "/documentos/dia", "/trabajos", "/tipos-documentos"):
        assert anonymous_client.get(path).status_code == 401, path


def test_login_with_email_and_password(anonymous_client, clean_db):
    create_user(clean_db, "Ana Admin", "ana@oxxo.cl", "ADMINISTRADOR")
    assert anonymous_client.post("/auth/login", json={"email": "ana@oxxo.cl", "contrasena": "mala"}).status_code == 401
    response = anonymous_client.post("/auth/login", json={"email": " ANA@oxxo.cl", "contrasena": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["usuario"] == {"id": body["usuario"]["id"], "nombre": "Ana Admin", "email": "ana@oxxo.cl", "rol": "ADMINISTRADOR"}
    me = anonymous_client.get("/auth/yo", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.json()["nombre"] == "Ana Admin"


def test_model_user_cannot_log_in(anonymous_client):
    response = anonymous_client.post("/auth/login", json={"email": "modelo-ia@sistema.local", "contrasena": "!"})
    assert response.status_code == 401
