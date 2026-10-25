-- Base de datos nueva, desde cero. Paso 1: roles y usuarios.

-- Roles de la aplicación (por ejemplo: administrador, revisor)
CREATE TABLE roles (
    id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rol       VARCHAR(50) NOT NULL UNIQUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Usuarios. Cada usuario tiene un rol; un rol puede tenerlo más de un usuario.
CREATE TABLE usuarios (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre          VARCHAR(150) NOT NULL,
    email           VARCHAR(255) NOT NULL,
    -- Nunca la contraseña en texto plano: solo su hash (bcrypt)
    contrasena_hash TEXT NOT NULL,
    id_rol          INTEGER NOT NULL REFERENCES roles (id) ON DELETE RESTRICT,
    creado_en       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- El email no se repite, sin importar mayúsculas (Ana@x.cl = ana@x.cl)
CREATE UNIQUE INDEX uq_usuarios_email ON usuarios (lower(email));
CREATE INDEX ix_usuarios_id_rol ON usuarios (id_rol);
