-- Paso 9: carpetas. Una carpeta subida (con sus subcarpetas) agrupa los documentos que salen de sus archivos.
-- El nombre puede repetirse: cada subida es una carpeta distinta.
CREATE TABLE carpetas (
    id         INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre     VARCHAR(255) NOT NULL,
    subida_en  TIMESTAMPTZ NOT NULL DEFAULT now(),
    id_usuario INTEGER NOT NULL REFERENCES usuarios (id) ON DELETE RESTRICT  -- quién la subió
);

CREATE INDEX ix_carpetas_subida_en ON carpetas (subida_en);

-- Los documentos de imágenes subidas sueltas (y los guardados antes de este paso) quedan sin carpeta
ALTER TABLE documentos_procesados
    ADD COLUMN id_carpeta INTEGER REFERENCES carpetas (id) ON DELETE RESTRICT;

CREATE INDEX ix_documentos_procesados_carpeta ON documentos_procesados (id_carpeta);
