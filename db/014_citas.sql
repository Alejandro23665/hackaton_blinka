-- Paso 14: solicitudes de cita desde la página pública (sin sesión). Las ve un administrador.
-- El teléfono se guarda separado: prefijo internacional (+56) y número sin espacios ni guiones.
-- El país desambigua los prefijos compartidos (+1: Estados Unidos, Canadá…).
CREATE TABLE citas (
    id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email     VARCHAR(255) NOT NULL,
    pais      CHAR(2)      NOT NULL CHECK (pais ~ '^[A-Z]{2}$'),
    prefijo   VARCHAR(5)   NOT NULL CHECK (prefijo ~ '^\+[0-9]{1,4}$'),
    telefono  VARCHAR(15)  NOT NULL CHECK (telefono ~ '^[0-9]{4,15}$'),
    creado_en TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX ix_citas_creado_en ON citas (creado_en);
