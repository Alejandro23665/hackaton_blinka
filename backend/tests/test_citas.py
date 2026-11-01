"""Citas: se piden sin sesión desde la página pública y solo un administrador las ve."""
import pytest

from app.api import citas
from app.auth import create_token
from tests.conftest import create_user

REQUEST = {"email": "compras@empresa.com", "pais": "cl", "prefijo": "+56", "telefono": "9 1234-5678"}


@pytest.fixture(autouse=True)
def no_rate_limit_carryover():
    citas._recent.clear()


def _as_admin(client, engine):
    admin_id = create_user(engine, "Ana Admin", "ana@oxxo.cl", "ADMINISTRADOR")
    client.headers["Authorization"] = f"Bearer {create_token(admin_id)}"


def test_anyone_can_request_an_appointment_and_only_an_admin_sees_it(anonymous_client, clean_db):
    client = anonymous_client
    assert client.post("/citas", json=REQUEST).status_code == 201
    # Sin sesión no se ven las citas
    assert client.get("/citas").status_code == 401

    _as_admin(client, clean_db)
    (cita,) = client.get("/citas").json()
    assert (cita["email"], cita["pais"], cita["prefijo"], cita["telefono"]) == ("compras@empresa.com", "CL", "+56", "912345678")


def test_a_reviewer_cannot_see_appointments(client):
    assert client.get("/citas").status_code == 403


def test_invalid_contact_data_is_rejected(anonymous_client):
    client = anonymous_client
    assert client.post("/citas", json={**REQUEST, "email": "sin-arroba"}).status_code == 422
    assert client.post("/citas", json={**REQUEST, "telefono": "12ab"}).status_code == 422
    assert client.post("/citas", json={**REQUEST, "prefijo": "56"}).status_code == 422
    # Más de 15 dígitos contando el prefijo no es un número internacional
    assert client.post("/citas", json={**REQUEST, "telefono": "1234567890123456"}).status_code == 422


def test_a_bot_filling_the_trap_field_is_ignored(anonymous_client, clean_db):
    client = anonymous_client
    assert client.post("/citas", json={**REQUEST, "sitio_web": "http://spam"}).status_code == 201
    _as_admin(client, clean_db)
    assert client.get("/citas").json() == []


def test_too_many_requests_from_the_same_address_are_slowed_down(anonymous_client):
    client = anonymous_client
    for _ in range(citas.LIMIT):
        assert client.post("/citas", json=REQUEST).status_code == 201
    assert client.post("/citas", json=REQUEST).status_code == 429
