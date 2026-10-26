-- Paso 5: quién procesó cada documento y revisión humana.
-- - Cada documento apunta a un usuario: el "Modelo IA" si lo procesó la IA, o la persona que lo corrigió.
-- - Se guardan los campos que faltan y los que tienen dudas, para mostrarlos en el formulario.
-- - Un documento revisado por una persona sale de la cola, aunque sea un descuadre real del documento.

INSERT INTO roles (rol) VALUES ('MODELO'), ('REVISOR'), ('ADMINISTRADOR');

-- Usuario de la IA. No puede iniciar sesión: '!' no es un hash de contraseña válido.
INSERT INTO usuarios (nombre, email, contrasena_hash, id_rol)
VALUES ('Modelo IA', 'modelo-ia@sistema.local', '!', (SELECT id FROM roles WHERE rol = 'MODELO'));

ALTER TABLE documentos_procesados ADD COLUMN id_usuario INTEGER REFERENCES usuarios (id) ON DELETE RESTRICT;
UPDATE documentos_procesados
SET id_usuario = (SELECT id FROM usuarios WHERE email = 'modelo-ia@sistema.local');
ALTER TABLE documentos_procesados ALTER COLUMN id_usuario SET NOT NULL;

-- Nombres de columna de los campos con problemas, por ejemplo {fecha,total_neto}
ALTER TABLE documentos_procesados
    ADD COLUMN campos_faltantes TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN campos_dudosos   TEXT[] NOT NULL DEFAULT '{}',
    ADD CONSTRAINT documentos_procesados_campos_check CHECK (
        campos_faltantes <@ ARRAY['rut_proveedor', 'folio', 'fecha', 'firma', 'total_neto', 'iva', 'impuestos', 'total']
        AND campos_dudosos <@ ARRAY['rut_proveedor', 'folio', 'fecha', 'firma', 'total_neto', 'iva', 'impuestos', 'total']
    );

-- Cuándo lo revisó una persona (vacío si nadie lo ha revisado)
ALTER TABLE documentos_procesados ADD COLUMN revisado_en TIMESTAMPTZ;

-- requiere_revision ahora también depende de la revisión: un documento revisado sale de la cola
DROP INDEX ix_documentos_procesados_revision;
ALTER TABLE documentos_procesados DROP COLUMN requiere_revision;
ALTER TABLE documentos_procesados
    ADD COLUMN requiere_revision BOOLEAN GENERATED ALWAYS AS (observaciones <> 'LEGIBLE' AND revisado_en IS NULL) STORED;
CREATE INDEX ix_documentos_procesados_revision ON documentos_procesados (creado_en) WHERE requiere_revision;

-- Totales por día del dashboard
CREATE INDEX ix_documentos_procesados_creado_en ON documentos_procesados (creado_en);
CREATE INDEX ix_documentos_procesados_usuario ON documentos_procesados (id_usuario);
