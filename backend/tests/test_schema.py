"""Las reglas que hace cumplir la propia base (archivos db/*.sql), sin pasar por el código."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

INSERT = text(
    "INSERT INTO documentos_procesados (rut_proveedor, folio, observaciones, id_tipo_documento, imagen) "
    "VALUES (:rut, :folio, :obs, (SELECT id FROM tipos_documentos WHERE documento = :tipo), 'originals/x.png') "
    "RETURNING requiere_revision"
)


def _insert(conn, rut="76084682-1", folio="1", obs="LEGIBLE", tipo="CI"):
    return conn.execute(INSERT, {"rut": rut, "folio": folio, "obs": obs, "tipo": tipo}).scalar_one()


def test_only_three_document_types(clean_db):
    with clean_db.connect() as conn:
        assert conn.execute(text("SELECT documento FROM tipos_documentos ORDER BY id")).scalars().all() == ["FC", "CI", "GD"]
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        conn.execute(text("INSERT INTO tipos_documentos (documento, descripcion) VALUES ('BO', 'Boleta')"))


def test_review_flag_is_computed_from_observations(clean_db):
    with clean_db.begin() as conn:
        assert [_insert(conn, folio=str(n), obs=obs) for n, obs in enumerate(("LEGIBLE", "NO_LEGIBLE", "DESCUADRE"))] == [
            False, True, True
        ]


def test_invalid_observation_is_rejected(clean_db):
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        _insert(conn, obs="DESCONOCIDO")


def test_unknown_type_cannot_be_stored(clean_db):
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        _insert(conn, tipo="BO")  # sin tipo: la columna es obligatoria


def test_same_document_cannot_be_stored_twice(clean_db):
    with clean_db.begin() as conn:
        _insert(conn)
        _insert(conn, tipo="FC")  # otro tipo: es otro documento
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        _insert(conn)


def test_substitute_rut_does_not_count_as_duplicate(clean_db):
    with clean_db.begin() as conn:
        _insert(conn, rut="1-9")
        _insert(conn, rut="1-9")


def test_negative_amounts_are_rejected(clean_db):
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO documentos_procesados (total, observaciones, id_tipo_documento, imagen) "
                "VALUES (-1, 'LEGIBLE', 1, 'originals/x.png')"
            )
        )


def test_user_email_is_unique_ignoring_case(clean_db):
    with clean_db.begin() as conn:
        role = conn.execute(text("INSERT INTO roles (rol) VALUES ('revisor') RETURNING id")).scalar_one()
        add = text("INSERT INTO usuarios (nombre, email, contrasena_hash, id_rol) VALUES ('Ana', :email, 'x', :rol)")
        conn.execute(add, {"email": "ana@oxxo.cl", "rol": role})
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        conn.execute(add, {"email": "ANA@oxxo.cl", "rol": role})
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        conn.execute(text("DELETE FROM roles"))  # un rol con usuarios no se borra
