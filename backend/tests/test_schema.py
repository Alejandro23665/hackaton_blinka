"""Las reglas que hace cumplir la propia base (archivos db/*.sql), sin pasar por el código."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

INSERT = text(
    "INSERT INTO documentos_procesados (rut_proveedor, folio, observaciones, id_tipo_documento, imagen, id_usuario) "
    "VALUES (:rut, :folio, :obs, (SELECT id FROM tipos_documentos WHERE documento = :tipo), 'originals/x.png', "
    "(SELECT id FROM usuarios WHERE email = 'modelo-ia@sistema.local')) "
    "RETURNING requiere_revision"
)


def _insert(conn, rut="76084682-1", folio="1", obs="LEGIBLE", tipo="CI"):
    return conn.execute(INSERT, {"rut": rut, "folio": folio, "obs": obs, "tipo": tipo}).scalar_one()


def test_only_three_document_types(clean_db):
    with clean_db.connect() as conn:
        assert conn.execute(text("SELECT * FROM tipos_documentos ORDER BY id")).all() == [(1, "FC"), (2, "CI"), (3, "GD")]
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        conn.execute(text("INSERT INTO tipos_documentos (documento) VALUES ('BO')"))


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
                "INSERT INTO documentos_procesados (total, observaciones, id_tipo_documento, imagen, id_usuario) "
                "VALUES (-1, 'LEGIBLE', 1, 'originals/x.png', 1)"
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


def test_reviewed_document_leaves_the_queue_and_field_names_are_checked(clean_db):
    with clean_db.begin() as conn:
        assert _insert(conn, obs="DESCUADRE") is True
        reviewed = conn.execute(
            text("UPDATE documentos_procesados SET revisado_en = now() RETURNING requiere_revision")
        ).scalar_one()
        assert reviewed is False
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        conn.execute(text("UPDATE documentos_procesados SET campos_dudosos = '{otro}'"))


def test_every_document_needs_a_user(clean_db):
    with pytest.raises(IntegrityError), clean_db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO documentos_procesados (observaciones, id_tipo_documento, imagen) "
                "VALUES ('LEGIBLE', 1, 'originals/x.png')"
            )
        )
