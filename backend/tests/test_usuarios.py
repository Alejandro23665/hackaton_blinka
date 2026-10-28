"""Perfiles: solo un administrador los ve y los cambia; un perfil desactivado no entra."""
import pytest

from app.auth import create_token
from app.core.config import settings
from app.usuarios import ensure_admin
from tests.conftest import PASSWORD, create_user


@pytest.fixture
def admin(anonymous_client, clean_db):
    admin_id = create_user(clean_db, "Ana Admin", "ana@oxxo.cl", "ADMINISTRADOR")
    anonymous_client.headers["Authorization"] = f"Bearer {create_token(admin_id)}"
    return anonymous_client, admin_id


def _login(client, email, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "contrasena": password}, headers={"Authorization": ""})


def test_only_an_admin_can_manage_profiles(client):
    # client inició sesión como revisora
    assert client.get("/usuarios").status_code == 403
    assert client.post("/usuarios", json={"nombre": "X", "email": "x@oxxo.cl", "rol": "REVISOR", "contrasena": "12345678"}).status_code == 403


def test_admin_lists_creates_and_changes_profiles(admin):
    client, _ = admin
    assert client.get("/usuarios/roles").json() == ["REVISOR", "ADMINISTRADOR"]
    created = client.post("/usuarios", json={"nombre": "Beto", "email": "beto@oxxo.cl", "rol": "revisor", "contrasena": "clave-segura"})
    assert created.status_code == 201
    beto = created.json()
    assert (beto["rol"], beto["activo"]) == ("REVISOR", True)
    assert _login(client, "beto@oxxo.cl", "clave-segura").status_code == 200

    # El Modelo IA no aparece
    assert [p["email"] for p in client.get("/usuarios").json()] == ["ana@oxxo.cl", "beto@oxxo.cl", "rita@oxxo.cl"]

    changed = client.patch(f"/usuarios/{beto['id']}", json={"rol": "ADMINISTRADOR"}).json()
    assert (changed["rol"], changed["activo"]) == ("ADMINISTRADOR", True)


def test_new_profile_is_validated(admin):
    client, _ = admin
    base = {"nombre": "Beto", "email": "beto@oxxo.cl", "rol": "REVISOR", "contrasena": "clave-segura"}
    assert client.post("/usuarios", json={**base, "contrasena": "corta"}).status_code == 422
    assert client.post("/usuarios", json={**base, "rol": "MODELO"}).status_code == 422
    assert client.post("/usuarios", json=base).status_code == 201
    repeated = client.post("/usuarios", json={**base, "email": "BETO@oxxo.cl"})
    assert repeated.status_code == 422 and "Ya existe" in repeated.json()["detail"]


def test_deactivated_profile_cannot_log_in_and_its_session_ends(admin, clean_db):
    client, _ = admin
    beto_id = create_user(clean_db, "Beto", "beto@oxxo.cl", "REVISOR")
    beto_session = {"Authorization": f"Bearer {create_token(beto_id)}"}
    assert client.get("/documentos", headers=beto_session).status_code == 200

    assert client.patch(f"/usuarios/{beto_id}", json={"activo": False}).json()["activo"] is False
    assert client.get("/documentos", headers=beto_session).status_code == 401
    refused = _login(client, "beto@oxxo.cl")
    assert refused.status_code == 403 and "desactivado" in refused.json()["detail"]

    client.patch(f"/usuarios/{beto_id}", json={"activo": True})
    assert _login(client, "beto@oxxo.cl").status_code == 200


def test_admin_cannot_lock_themself_out_or_touch_the_model(admin, session):
    client, admin_id = admin
    assert client.patch(f"/usuarios/{admin_id}", json={"activo": False}).status_code == 400
    assert client.patch(f"/usuarios/{admin_id}", json={"rol": "REVISOR"}).status_code == 400
    assert client.patch(f"/usuarios/{admin_id}", json={"rol": "ADMINISTRADOR"}).status_code == 200
    from app.pipeline.process import model_user_id

    assert client.patch(f"/usuarios/{model_user_id(session)}", json={"activo": False}).status_code == 404


def test_initial_admin_is_created_once_from_settings(session, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAIL", None)
    assert "define ADMIN_EMAIL" in ensure_admin(session)

    monkeypatch.setattr(settings, "ADMIN_NOMBRE", "Jefa")
    monkeypatch.setattr(settings, "ADMIN_EMAIL", "jefa@oxxo.cl")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", "clave-inicial")
    assert "creado" in ensure_admin(session)
    assert "ya existe" in ensure_admin(session)
    from app.usuarios import roles
    from app.models import Usuario
    from sqlmodel import select

    jefa = session.exec(select(Usuario).where(Usuario.email == "jefa@oxxo.cl")).one()
    assert (jefa.nombre, jefa.id_rol, jefa.activo) == ("Jefa", roles(session)["ADMINISTRADOR"], True)
